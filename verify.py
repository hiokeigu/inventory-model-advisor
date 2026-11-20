import numpy as np
import engine as e
def original_simulate(F, carrying_rate, penalty_fraction):
    n=len(products)
    h=COST*carrying_rate/52
    penalty=PRICE*MARGIN*penalty_fraction
    on_hand=INITIAL.copy(); pipeline=np.zeros(n)
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
        on_hand[new]=past.fillna(0).mean().to_numpy()[new]
        initial_units+=on_hand[new].sum()
        initialized |= new
        on_hand+=pipeline; received+=pipeline.sum(); pipeline=np.zeros(n)
        eligible=known
        idx=np.where(eligible)[0]
        q_all=np.zeros(n)
        if t!=sim_weeks[-1] and len(idx):
            f=F[t,idx]
            base=np.maximum(on_hand[idx]-f,0)
            z=residual_quantiles(F,t,1,N_SCENARIOS)
            scen=f[:,None] if z is None else np.maximum(f[:,None]+z[None,:]*np.sqrt(np.maximum(f,1))[:,None],0)
            budget=1.25*float(RUN_RATE[t,idx]@COST[idx])
            q=solve_order_lp(base,scen,h[idx],penalty[idx],COST[idx],budget)
            assert q@COST[idx]<=budget+1e-5
            q_all[idx]=q; pipeline=q_all.copy(); spend+=q@COST[idx]
        orders.append(q_all)
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

# Source function uses the validated engine namespace.
original_simulate.__globals__.update({k:v for k,v in vars(e).items() if not k.startswith('__')})
for model in e.METHODS:
    expected,_=original_simulate(e.F[model],.15,.5)
    actual,_=e.simulate(e.F[model],.15,.5)
    for key in expected:
        assert np.isclose(expected[key],actual[key],rtol=1e-9,atol=1e-5),(model,key)
base=e.evaluate(.15,.5,1.,1,1.25)
assert len(base)==7 and base.Pareto.any()
for args in [(.35,.5,1.,1,1.25),(.15,1.,1.,1,1.25),(.15,.5,.5,1,1.25),(.15,.5,1.,2,1.25),(.15,.5,1.,1,.5),(.15,.5,1.,0,1.25)]:
    changed=e.evaluate(*args)
    assert not np.allclose(base.Total_Simulated_Cost,changed.Total_Simulated_Cost),args
assert np.isfinite(base.select_dtypes('number')).all().all()
print(base.to_string(index=False))
print('PASS: seven source models reproduced; all five parameters affect real simulation; lead 0/2 run; inventory and budget checks pass.')

