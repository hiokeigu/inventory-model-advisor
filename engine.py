from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog
DATA_DIR=Path(__file__).parent / 'data'
REQUIRED_FILES=['demand_dataset_A.csv','selected_six_model_predictions.csv','dataco_order_fields.csv.gz']
if not DATA_DIR.is_dir(): raise FileNotFoundError(f'Missing project folder: {DATA_DIR}')
missing=[name for name in REQUIRED_FILES if not (DATA_DIR/name).is_file()]
if missing: raise FileNotFoundError(f'Missing CSV files in {DATA_DIR}: {missing}. Available CSVs: {sorted(x.name for x in DATA_DIR.glob("*.csv"))}')
MARGIN = .3318
START, END = pd.Timestamp('2017-04-03'), pd.Timestamp('2017-09-25')
WARMUP = pd.Timestamp('2017-02-06')
MODELS = ['XGBoost','LightGBM','Ridge','Lasso','Linear Regression','Poisson Regression']
SCENARIOS = {'S1 — Low / Low':(.15,.5),'S2 — High Holding':(.35,.5),
             'S3 — High Stockout':(.15,1.),'S4 — High / High':(.35,1.)}
N_SCENARIOS, MIN_RESIDUALS = 41, 30
raw = pd.read_csv((DATA_DIR / 'demand_dataset_A.csv'),encoding='utf-8-sig')
preds = pd.read_csv((DATA_DIR / 'selected_six_model_predictions.csv'))
price_path = (DATA_DIR / 'dataco_order_fields.csv.gz')
# Read only required fields; customer data are not used.
dataco = pd.read_csv(price_path,encoding='latin1',usecols=[
 'Product Card Id','order date (DateOrders)','Order Item Product Price',
 'Order Item Quantity','Sales'])
assert {'product_id','forecast_week','actual_order_qty'} <= set(raw)
assert {'Model','Window','product_id','forecast_week','actual','prediction','train_end'} <= set(preds)
raw['forecast_week']=pd.to_datetime(raw.forecast_week)
preds['forecast_week']=pd.to_datetime(preds.forecast_week)
preds['train_end']=pd.to_datetime(preds.train_end)
assert not raw.duplicated(['product_id','forecast_week']).any()
assert set(preds.Model)==set(MODELS)
assert (preds.train_end < preds.forecast_week).all(), 'Forecast training leakage'
assert (raw.actual_order_qty>=0).all()
selected=preds.groupby('Model').Window.agg(lambda x: sorted(set(x)))
assert selected.map(len).eq(1).all(), 'Each model must have one selected training window'

weeks=pd.date_range(WARMUP,END,freq='W-MON')
products=np.array(sorted(raw.loc[raw.forecast_week<=END,'product_id'].unique()))
def matrix(frame,col):
    return frame.pivot(index='forecast_week',columns='product_id',values=col).reindex(index=weeks,columns=products).to_numpy(float)
ACTUAL=matrix(raw,'actual_order_qty')
ACTIVE=np.isfinite(ACTUAL)
F={}
keys=['product_id','forecast_week']
expected=raw.loc[raw.forecast_week.between(WARMUP,END)].set_index(keys).actual_order_qty.sort_index()
for model in MODELS:
    s=preds.loc[(preds.Model==model)&preds.forecast_week.between(WARMUP,END)]
    assert not s.duplicated(keys).any()
    check=s.set_index(keys).sort_index()
    assert check.index.equals(expected.index), f'{model}: product-week coverage differs'
    assert np.allclose(check.actual,expected), f'{model}: observed demand mismatch'
    assert np.isfinite(check.prediction).all()
    F[model]=np.maximum(pd.DataFrame(matrix(s,'prediction')).ffill().fillna(0).to_numpy(),0)
# Verify per-unit selling price using the line-sales identity, before simulation only.
dataco['date']=pd.to_datetime(dataco['order date (DateOrders)'])
hist=dataco.loc[dataco.date<START].copy()
assert np.allclose(hist['Order Item Product Price']*hist['Order Item Quantity'],hist.Sales,rtol=1e-5,atol=.02), 'Unit-price identity failed'
# New assortment SKUs have no pre-start price: freeze their median at first eligible entry.
first_seen=raw.groupby('product_id').forecast_week.min()
price_values=[]
for sku in products:
    cutoff=max(START, pd.Timestamp(first_seen.loc[sku])+pd.Timedelta(days=7))
    price_values.append(dataco.loc[(dataco['Product Card Id']==sku)&(dataco.date<cutoff),'Order Item Product Price'].median())
prices=pd.Series(price_values,index=products)
assert prices.notna().all() and prices.gt(0).all(), 'Missing historical SKU prices'
PRICE=prices.to_numpy(); COST=PRICE*(1-MARGIN)
# Cross-check the historical quantity source against the product-week dataset.
dataco['forecast_week']=dataco.date.dt.to_period('W-SUN').dt.start_time
qty=dataco.groupby(['Product Card Id','forecast_week'])['Order Item Quantity'].sum()
qty.index.names=keys
joined=raw.set_index(keys).actual_order_qty.to_frame().join(qty.rename('raw_qty'))
quantity_mismatches=int((~np.isclose(joined.actual_order_qty,joined.raw_qty.fillna(0))).sum())
calendar=pd.date_range(raw.forecast_week.min(),END,freq='W-MON')
wide=raw.pivot(index='forecast_week',columns='product_id',values='actual_order_qty').reindex(index=calendar,columns=products)
RUN_RATE=wide.fillna(0).shift(1).rolling(4,min_periods=1).mean().reindex(weeks).fillna(0).to_numpy()
# Means span the full historical calendar, including weeks with no recorded quantity.
pre=wide.loc[wide.index<START]
INITIAL=pre.fillna(0).mean().to_numpy()
assert np.isfinite(INITIAL).all()
seen_before=pre.notna().any().to_numpy()
sim_weeks=np.where(weeks>=START)[0]

BASELINE='4-Week Moving Average Baseline'
# Four calendar weeks, excluding current week; unknown records are not zero observations.
baseline_history=wide.shift(1).rolling(window=4,min_periods=1).mean()
# No observations in the preceding four weeks: preserve the zero forecast fallback.
# This is a replenishment decision fallback, not an imputed actual-demand observation.
F[BASELINE]=baseline_history.reindex(weeks).fillna(0).to_numpy()
assert np.allclose(F[BASELINE],wide.shift(1).rolling(4,min_periods=1).mean().reindex(weeks).fillna(0).to_numpy())
METHODS=[BASELINE]+MODELS

# 4. OPTIMIZATION MODEL
def solve_order_lp(base, scen, h, p, unit_cost, budget):
    # base: (n,) stock before ordering; scen: (n, K) demand scenarios.
    # Returns order quantities q (n,) minimizing expected holding + lost-margin cost within budget.
    n, K = scen.shape
    if n == 0:
        return np.zeros(0)
    nk = n * K
    rows = np.arange(nk)
    prod_of_row = np.repeat(np.arange(n), K)
    # Variables: [q (n) | o (nK) | u (nK)]
    # q_i - o_ik <= d_ik - b_i
    A1 = sparse.csr_matrix((np.r_[np.ones(nk), -np.ones(nk)],
                            (np.r_[rows, rows], np.r_[prod_of_row, n + rows])), shape=(nk, n + 2 * nk))
    # -q_i - u_ik <= b_i - d_ik
    A2 = sparse.csr_matrix((np.r_[-np.ones(nk), -np.ones(nk)],
                            (np.r_[rows, rows], np.r_[prod_of_row, n + nk + rows])), shape=(nk, n + 2 * nk))
    A3 = sparse.csr_matrix((np.asarray(unit_cost), (np.zeros(n, int), np.arange(n))), shape=(1, n + 2 * nk))
    d = scen.ravel()
    b = np.repeat(base, K)
    A_ub = sparse.vstack([A1, A2, A3], format="csr")
    b_ub = np.r_[d - b, b - d, budget]
    cost = np.r_[np.zeros(n), np.repeat(h / K, K), np.repeat(p / K, K)]
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
    if res.status != 0:
        raise RuntimeError(f"LP failed: {res.message}")
    return np.clip(res.x[:n], 0, None)


def residual_quantiles(F, t, lead, n_scen):
    # Standardized past errors known at the START of week t (no future data).
    # lead 0: error of week s forecast for week s, for s < t.
    # lead 1: error of forecast F[s] used for week s+1, for s+1 < t (2-week-ahead error).
    if lead == 0:
        A, P, ok = ACTUAL[:t], F[:t], ACTIVE[:t]
    else:
        if t <= lead:
            return None
        A, P, ok = ACTUAL[lead:t], F[:t - lead], ACTIVE[lead:t] & ACTIVE[:t - lead]
    z =(A[ok] - P[ok]) / np.sqrt(np.maximum(P[ok], 1.0))
    if z.size < MIN_RESIDUALS:
        return None
    levels = (np.arange(n_scen) + 0.5) / n_scen
    return np.quantile(z, levels)
def simulate(F, carrying_rate, penalty_fraction, initial_mult=1., lead=1, budget_mult=1.25, holding_per_unit_week=None, penalty_per_unit=None, budget_per_week=None, decision_log=None):
    n=len(products)
    h=COST*carrying_rate/52 if holding_per_unit_week is None else np.full(n,holding_per_unit_week)
    penalty=PRICE*MARGIN*penalty_fraction if penalty_per_unit is None else np.full(n,penalty_per_unit)
    on_hand=INITIAL.copy()*initial_mult; arrivals=np.zeros((len(weeks)+lead+1,n))
    initialized=seen_before.copy()
    inventory_ends=[]
    orders=[]; holding=lost_cost=unmet=demand=spend=0.
    received=sold_total=0.
    initial_units=on_hand.sum()
    for t in sim_weeks:
        week=weeks[t]
        past=wide.loc[wide.index<week]
        known=past.notna().any().to_numpy()
        # Previously unseen SKUs may enter only after their first completed observed week.
        new=known & ~initialized
        on_hand[new]=past.fillna(0).mean().to_numpy()[new]*initial_mult
        initial_units+=on_hand[new].sum()
        initialized |= new
        on_hand+=arrivals[t]; received+=arrivals[t].sum()
        eligible=known
        idx=np.where(eligible)[0]
        q_all=np.zeros(n)
        starting_inventory=on_hand.copy() if decision_log is not None else None
        weekly_budget=budget_mult*float(RUN_RATE[t,idx]@COST[idx]) if budget_per_week is None else budget_per_week
        order_allowed=t+lead<=sim_weeks[-1] and len(idx)>0
        if t+lead<=sim_weeks[-1] and len(idx):
            f=F[t,idx]
            base=np.maximum(on_hand[idx]+arrivals[t+1:t+lead+1,idx].sum(axis=0)-lead*f,0)
            z=residual_quantiles(F,t,lead,N_SCENARIOS)
            scen=f[:,None] if z is None else np.maximum(f[:,None]+z[None,:]*np.sqrt(np.maximum(f,1))[:,None],0)
            budget=budget_mult*float(RUN_RATE[t,idx]@COST[idx]) if budget_per_week is None else budget_per_week
            q=solve_order_lp(base,scen,h[idx],penalty[idx],COST[idx],budget)
            assert q@COST[idx]<=budget+1e-5
            q_all[idx]=q; spend+=q@COST[idx]
            if lead==0:
                on_hand+=q_all; received+=q_all.sum()
            else:
                arrivals[t+lead]+=q_all
        orders.append(q_all)
        if decision_log is not None:
            assert float(q_all@COST)<=weekly_budget+1e-5
            for i in idx:
                decision_log.append(dict(Week=week,SKU=products[i],
                    Starting_Inventory=float(starting_inventory[i]),Forecast_Demand=float(F[t,i]),
                    Recommended_Order_Quantity=float(q_all[i]),Unit_Purchase_Cost=float(COST[i]),
                    Estimated_Purchase_Cost=float(q_all[i]*COST[i]),
                    Weekly_Purchasing_Budget=float(weekly_budget),Order_Allowed=bool(order_allowed)))
        dem=np.nan_to_num(ACTUAL[t])
        sold=np.minimum(on_hand,dem); on_hand-=sold
        shortage=dem-sold
        demand+=dem.sum(); unmet+=shortage.sum(); sold_total+=sold.sum()
        lost_cost+=float(shortage@penalty); holding+=float(on_hand@h)
        inventory_ends.append(on_hand.sum())
    assert np.isclose(initial_units+received,sold_total+on_hand.sum(),atol=1e-4)
    assert np.isclose(sold_total+unmet,demand)
    return dict(Total_Simulated_Cost=holding+lost_cost,
                Fill_Rate=1-unmet/demand,Unmet_Demand_Units=unmet,
                Average_Ending_Inventory=float(np.mean(inventory_ends)),
                Holding_Cost=holding,Lost_Sales_Penalty=lost_cost,Final_Inventory_Units=float(on_hand.sum()),Final_Inventory_Value=float(on_hand@COST)),np.array(orders)

def evaluate(carry, penalty, initial, lead, budget, holding_per_unit_week=None, penalty_per_unit=None, budget_per_week=None, include_plans=False):
    rows=[]
    plans=[]
    for model in METHODS:
        log=[] if include_plans else None
        result,_=simulate(F[model],carry,penalty,initial,lead,budget,holding_per_unit_week,penalty_per_unit,budget_per_week,decision_log=log)
        if include_plans:
            plans.extend(dict(Model=model,**entry) for entry in log)
        rows.append(dict(Model=model,**result))
    frame=pd.DataFrame(rows)
    c=frame.Total_Simulated_Cost.to_numpy(); f=frame.Fill_Rate.to_numpy()
    frame['Pareto']= [not np.any((c<=c[i]) & (f>=f[i]) & ((c<c[i]) | (f>f[i]))) for i in range(len(c))]
    return (frame,pd.DataFrame(plans)) if include_plans else frame

