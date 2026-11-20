from html import escape
import hashlib
import importlib.util
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='Inventory Model Advisor', page_icon='◌', layout='wide', menu_items={'Get Help':None,'Report a bug':None,'About':None})
st.markdown('''<style>
.stApp {background:#f8f6ef;color:#293c30} 
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], #MainMenu, footer {display:none!important}
.block-container {max-width:1440px;padding-top:1.2rem}
h1,h2,h3 {font-weight:500!important;letter-spacing:-.035em}
h1 {font-family:Georgia,serif;font-size:3.1rem!important}
.st-key-business_inputs {background:#eeeee4;border:1px solid #d9dfd2;border-radius:12px;padding:20px}
.st-key-business_inputs [data-testid="stVerticalBlock"] {gap:.65rem}
.eyebrow {font-size:.74rem;letter-spacing:.18em;color:#6d806e;text-transform:uppercase}
.recommendation {background:#e6eddf;border:1px solid #d8e1d0;border-radius:10px;min-height:78px;box-sizing:border-box;padding:14px 20px;display:flex;flex-direction:column;justify-content:center;gap:4px}
.recommendation-title {font-size:1rem;line-height:1.4;color:#304c38}
.muted {color:#758071;font-size:.9rem}
[data-testid="stMetric"] {background:#fffdf7;border:1px solid #d9dfd2;border-radius:12px;padding:16px 12px}
[data-testid="stMetricLabel"] {font-size:.8rem;color:#6d806e}
[data-testid="stMetricValue"] {font-family:Georgia,serif;font-size:clamp(1.4rem,2.3vw,2.5rem)}
.st-key-business_inputs [data-testid="stSegmentedControl"] button {border-radius:20px;font-size:.78rem;padding:4px 9px}
.st-key-business_inputs [data-testid="stNumberInput"] input {border-radius:24px}
.st-key-business_inputs hr {margin:.5rem 0}
.stButton button {background:#526b50;color:white;border:0;border-radius:10px}
</style>''', unsafe_allow_html=True)

ENGINE_PATH=Path(__file__).with_name('engine.py')
ENGINE_REVISION=hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()

@st.cache_resource
def load_backend(revision):
    # Load this source revision, rather than reusing an older imported engine.
    spec=importlib.util.spec_from_file_location('inventory_engine_'+revision,ENGINE_PATH)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def backend():
    return load_backend(ENGINE_REVISION)

@st.cache_data(show_spinner=False, max_entries=32)
def calculate(parameters, revision):
    carry,penalty,initial,lead,budget,holding_fixed,penalty_fixed,budget_fixed=parameters
    return load_backend(revision).evaluate(
        carry=carry,penalty=penalty,initial=initial,lead=lead,budget=budget,
        holding_per_unit_week=holding_fixed,penalty_per_unit=penalty_fixed,
        budget_per_week=budget_fixed,include_plans=True)


def unit_switch(title, options, key):
    heading, switch = st.columns([1, 1.6], vertical_alignment='center')
    heading.markdown(f'**{title}**')
    return switch.segmented_control(title+' units', options, default=options[0],
                                    selection_mode='single', required=True,
                                    label_visibility='collapsed', key=key)

st.title('Inventory Model Advisor')
inputs_column,results_column=st.columns([3,7],gap='large')

with inputs_column, st.container(key='business_inputs'):
    st.markdown('### Business Objective')
    objective=st.radio('Business Objective',['Minimize Total Operating Cost','Maximize Fill Rate','Balanced (Pareto)'],label_visibility='collapsed',key='business_objective')
    st.markdown('### Business Inputs')
    holding_mode=unit_switch('Holding Cost',['% / Year','$/Unit/Week'],'holding_unit_tabs')
    carry=.15
    holding_fixed=None
    if holding_mode=='% / Year':
        carry=st.number_input('Holding Cost (% / Year)',min_value=0.,value=15.,step=1.,key='holding_percent',help='Annual percentage of each SKU’s estimated purchase cost; divided by 52 for weekly holding cost.')/100
    else:
        holding_fixed=st.number_input('Holding Cost ($/Unit/Week)',min_value=0.,value=.10,step=.01,key='holding_fixed',help='The same weekly dollar charge per remaining unit across SKUs.')
    st.divider()
    penalty_mode=unit_switch('Stockout Penalty',['% of Gross Profit','$/Unit'],'penalty_unit_tabs')
    penalty=.5
    penalty_fixed=None
    if penalty_mode=='% of Gross Profit':
        penalty=st.number_input('Stockout Penalty (% of Gross Profit)',min_value=0.,value=50.,step=10.,key='penalty_percent',help='Per unmet unit: SKU estimated unit gross profit × selected percentage / 100. Gross profit uses historical DataCo selling price and the assumed 33.18% margin.')/100
    else:
        penalty_fixed=st.number_input('Stockout Penalty ($/Unit)',min_value=0.,value=10.,step=1.,key='penalty_fixed',help='Applied to every unmet unit across SKUs. SKU-specific penalties would require company data.')
    st.divider()
    st.markdown('**Current Inventory** · DataCo Demo')
    initial=st.number_input('Current Inventory (× Average Weekly Demand)',min_value=0.,value=1.,step=.25,key='current_inventory',help='Demo starting inventory = historical average weekly recorded DataCo demand × multiplier, before simulation or first eligible SKU entry. For 10 units/week, 1.5× means 15 units. Missing calendar weeks contribute zero to this reference mean; they do not confirm zero true demand. Actual SKU inventory is a future extension.')
    st.divider()
    lead=st.selectbox('Lead Time',[1,2,3],format_func=lambda value:f'{value} week'+('s' if value!=1 else ''),key='lead_time_weekly')
    st.divider()
    budget_mode=unit_switch('Purchasing Budget',['Multiplier','$/Week'],'budget_unit_tabs')
    budget=1.25
    budget_fixed=None
    if budget_mode=='Multiplier':
        budget=st.number_input('Purchasing Budget (× Recent Weekly Cost)',min_value=0.,value=1.25,step=.05,key='budget_multiplier',help='Weekly limit = multiplier × previous four calendar weeks’ average recorded DataCo demand, valued at estimated SKU purchase cost and summed across eligible SKUs. A $1,000 reference at 1.25× permits $1,250 of orders. Missing quantities contribute zero; this is a demand-based reference, not observed purchasing spend.')
    else:
        budget_fixed=st.number_input('Purchasing Budget ($/Week)',min_value=0.,value=10000.,step=100.,key='budget_fixed',help='This dollar amount directly caps total order purchase cost each week.')
    submitted=st.button('Apply Changes',type='primary',width='stretch')
    draft_parameters=(carry,penalty,initial,lead,budget,holding_fixed,penalty_fixed,budget_fixed)

with results_column:
    kpi_cards=st.container()
    try:
        applied=st.session_state.get('applied_simulation',{})
        if (not applied or 'plans' not in applied or applied.get('revision')!=ENGINE_REVISION or
                (submitted and applied.get('parameters')!=draft_parameters)):
            with st.spinner('Simulating seven methods with weekly LP optimization…'):
                computed,plans=calculate(draft_parameters,ENGINE_REVISION)
            st.session_state.applied_simulation={'result':computed,'plans':plans,'parameters':draft_parameters,'revision':ENGINE_REVISION}
        result=st.session_state.applied_simulation['result']
        engine=backend()
    except Exception as exc:
        st.error(f'Simulation unavailable: {exc}')
        st.info('No example results are substituted. See README for the required DataCo files and dependencies.')
        st.stop()
    
    if objective=='Balanced (Pareto)':
        candidates=result.loc[result.Pareto]
        label='Recommended Models'
        reason='Pareto-efficient cost and fill-rate trade-offs under the selected conditions.'
    elif objective=='Maximize Fill Rate':
        candidates=result.loc[result.Fill_Rate==result.Fill_Rate.max()]
        label='Recommended Model' if len(candidates)==1 else 'Recommended Models · exact tie'
        reason='Highest estimated fill rate under the selected conditions.'
    else:
        candidates=result.loc[result.Total_Simulated_Cost==result.Total_Simulated_Cost.min()]
        label='Recommended Model' if len(candidates)==1 else 'Recommended Models · exact tie'
        reason='Lowest estimated total operating cost under the selected conditions.'
    names=' · '.join(escape(x) for x in candidates.Model)
    st.markdown(f'<div class="recommendation"><div class="recommendation-title"><strong>{label}:</strong> {names}</div><div class="muted">{reason}</div></div>',unsafe_allow_html=True)
    if len(candidates)>1:
        chosen=st.selectbox('Inspect candidate metrics',candidates.Model.tolist())
        row=candidates.loc[candidates.Model==chosen].iloc[0]
    else:
        row=candidates.iloc[0]
    with kpi_cards:
        a,b,c=st.columns(3)
        a.metric('Estimated Total Operating Cost',f'${row.Total_Simulated_Cost:,.2f}')
        b.metric('Fill Rate',f'{row.Fill_Rate:.2%}')
        c.metric('Ending Inventory Value',f'${row.Final_Inventory_Value:,.2f}')
    st.markdown('### Model Comparison')
    table=result[['Model','Total_Simulated_Cost','Fill_Rate','Final_Inventory_Value','Pareto']].rename(columns={'Total_Simulated_Cost':'Total Operating Cost','Fill_Rate':'Fill Rate','Final_Inventory_Value':'Ending Inventory Value','Pareto':'Pareto efficient'})
    from comparison_table import render_comparison
    render_comparison(table, candidates.Model.tolist())
    st.caption('DataCo recorded demand · 26 evaluation weeks · Apr 3–Sep 25, 2017 · Live LP simulation')
    st.download_button('Download current comparison',result.to_csv(index=False),'inventory_comparison.csv','text/csv')
    st.markdown('### Replenishment Plan')
    st.caption('Historical simulated DataCo replenishment decisions — not live purchase recommendations or today’s inventory.')
    plans=st.session_state.applied_simulation['plans']
    model_plans=plans.loc[plans.Model.eq(row.Model)]
    plan_weeks=sorted(model_plans.Week.unique())
    selected_week=st.selectbox('Simulation week',plan_weeks,index=len(plan_weeks)-1,
        format_func=lambda value:engine.pd.Timestamp(value).strftime('%b %d, %Y'),key='plan_week')
    plan=model_plans.loc[model_plans.Week.eq(selected_week)].copy()
    units=float(plan.Recommended_Order_Quantity.sum())
    purchase_cost=float(plan.Estimated_Purchase_Cost.sum())
    week_budget=float(plan.Weekly_Purchasing_Budget.iloc[0])
    assert purchase_cost<=week_budget+1e-5
    st.caption(f'Model: {row.Model} · Weekly purchasing budget: ${week_budget:,.2f}')
    if not plan.Order_Allowed.any():
        st.caption('No replenishment order: arrival would fall beyond the evaluation horizon.')
    u,v=st.columns(2)
    u.metric('Total Replenishment Units',f'{units:,.2f}')
    v.metric('Estimated Purchase Cost',f'${purchase_cost:,.2f}')
    st.caption('Starting inventory is simulated on-hand stock after scheduled receipts and before this week’s order and demand. Forecast Demand is the model forecast used by the policy; the LP also uses its historical error buffer. Eligible SKUs include zero-order rows; quantities are continuous.')
    plan_table=plan[['SKU','Starting_Inventory','Forecast_Demand','Recommended_Order_Quantity','Estimated_Purchase_Cost']].rename(columns={
        'Starting_Inventory':'Starting Inventory','Forecast_Demand':'Forecast Demand',
        'Recommended_Order_Quantity':'Recommended Order Quantity','Estimated_Purchase_Cost':'Estimated Purchase Cost'})
    st.dataframe(plan_table.style.format({'Starting Inventory':'{:,.2f}','Forecast Demand':'{:,.2f}',
        'Recommended Order Quantity':'{:,.2f}','Estimated Purchase Cost':'${:,.2f}'}),hide_index=True,width='stretch')
    export=plan.assign(Context='Historical DataCo simulation; not live purchasing advice')
    st.download_button('Download replenishment plan CSV',export.to_csv(index=False),
        f'replenishment_{engine.pd.Timestamp(selected_week):%Y-%m-%d}_{row.Model.replace(" ","_")}.csv','text/csv')
    with st.expander('Model Notes & Assumptions'):
        st.table({
            'Area':['Forecasting models','Forecasting uncertainty','Optimization','Cost calculation','Inventory treatment','Lead time','Dataset'],
            'Summary':['Six trained models + four-week moving average baseline',
                       'Model-specific historical error buffers',
                       'Weekly budget-constrained linear programming',
                       'Holding cost + stockout penalty',
                       'Carried forward; no automatic write-off',
                       'Current forecast approximates future demand',
                       'DataCo historical orders · 26-week simulation']
        })
        st.caption('Limitations: recorded orders proxy demand; forecasts stay fixed. Lead time uses an approximation. Retrospective model-window selection may introduce selection bias.')
    with st.expander('Technical Details'):
        st.write('Selected model windows: '+', '.join(f'{m} ({engine.selected[m][0]})' for m in engine.MODELS))
        st.write('The linked notebook supplies forecasts and model-specific historical residual buffers. Applied operating assumptions feed weekly LPs; identical parameter combinations are cached.')
        st.write('Purchasing spend constrains orders. Ending inventory is a separate asset / capital commitment. Quantities are continuous and the optimizer is myopic; orders arriving after the evaluation horizon are suppressed.')
        st.write('Lead time carries the current forecast to the arrival week rather than fitting multi-step forecasts. Missing demand records remain unknown; initialization and budget retain the source’s zero-contribution convention. Model-window selection may overlap evaluation weeks.')
        st.write('Company-owned dataset upload: Future Extension.')
    st.link_button('Source Colab Notebook','https://colab.research.google.com/drive/11l4MoVEO3ISTK1oTFFPnQTCF_EtvD9HN')

