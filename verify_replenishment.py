"""Verify captured decisions against LP outputs and dashboard selection."""
from io import StringIO
from unittest.mock import patch
import numpy as np
import pandas as pd
import streamlit as st
import engine as e
from plan_views import POISSON, SPEND, UNITS, comparison_summary, sku_changes, sku_details
from scipy.optimize import linprog
from streamlit.testing.v1 import AppTest

for lead,budget_fixed in [(1,None),(2,10000.),(3,None)]:
    for model in e.METHODS:
        records=[]
        baseline,expected_orders=e.simulate(e.F[model],.15,.5,1.,lead,1.25,budget_per_week=budget_fixed)
        metrics,orders=e.simulate(e.F[model],.15,.5,1.,lead,1.25,budget_per_week=budget_fixed,decision_log=records)
        assert np.array_equal(expected_orders,orders)
        for key in baseline:
            assert np.isclose(baseline[key],metrics[key])
        frame=e.pd.DataFrame(records)
        if model==POISSON:
            source_names=e.raw.groupby('product_id').product_name.first()
            assert frame.Product_Name.eq(frame.SKU.map(source_names)).all()
            assert frame.Arrival_Week.sub(frame.Week).dt.days.eq(7*lead).all()
            allowed=frame.loc[frame.Order_Allowed]
            projected=(allowed.Starting_Inventory+allowed.Scheduled_Inbound_Units-lead*allowed.Forecast_Demand).clip(lower=0)
            assert np.allclose(allowed.Projected_Stock_Before_New_Order,projected)
            outcome=frame.Simulated_Fulfilled_Units+frame.Simulated_Unmet_Units
            assert np.allclose(outcome,frame.Recorded_Order_Units,equal_nan=True)
        for j,t in enumerate(e.sim_weeks):
            week=frame[frame.Week.eq(e.weeks[t])]
            positions=[np.where(e.products==sku)[0][0] for sku in week.SKU]
            assert np.array_equal(week.Recommended_Order_Quantity,orders[j,positions])
            assert np.allclose(week.Estimated_Purchase_Cost,orders[j,positions]*e.COST[positions])
            assert np.isclose(week.Estimated_Purchase_Cost.sum(),orders[j]@e.COST)
            assert week.Estimated_Purchase_Cost.sum()<=week.Weekly_Purchasing_Budget.iloc[0]+1e-5
            assert np.allclose(week.Forecast_Demand,e.F[model][t,positions])
        assert frame[frame.Week.eq(e.weeks[e.sim_weeks[-1]])].Recommended_Order_Quantity.eq(0).all()
print('PASS: captured SKU orders exactly match simulation/LP arrays, all weeks and models; costs and budgets match; metrics unchanged for leads 1/2/3.')

with patch('scipy.optimize.linprog',wraps=linprog) as lp, patch.object(st,'download_button',wraps=st.download_button) as downloads:
    def exported(label):
        call=next(call for call in reversed(downloads.call_args_list) if call.args[0]==label)
        return pd.read_csv(StringIO(call.args[1])).set_index('SKU').sort_index()

    app=AppTest.from_file('app.py',default_timeout=120).run()
    assert not app.exception and not app.error
    count=lp.call_count
    assert app.selectbox(key='plan_week').value==e.weeks[e.sim_weeks[-2]]
    app.selectbox(key='plan_week').set_value(e.END).run()
    assert app.metric[3].value=='0.00'
    assert any('would arrive after the replay' in item.value for item in app.info)
    app.selectbox(key='plan_week').set_value(e.weeks[e.sim_weeks[-2]]).run()
    assert lp.call_count==count
    app.radio[0].set_value('Balanced (Pareto)').run()
    candidates=[x for x in app.selectbox if x.label=='Inspect candidate metrics']
    for name in candidates[0].options:
        [x for x in app.selectbox if x.label=='Inspect candidate metrics'][0].select(name).run()
        assert not app.exception and not app.error
        assert lp.call_count==count
        state=app.session_state.applied_simulation
        plan=state['plans'].loc[lambda x:x.Model.eq(name)&x.Week.eq(app.selectbox(key='plan_week').value)]
        assert app.metric[3].value==f'{plan.Recommended_Order_Quantity.sum():,.2f}'
        assert app.metric[4].value==f'${plan.Estimated_Purchase_Cost.sum():,.2f}'
        assert len(app.dataframe[0].value)==len(plan)
    weekly_csv=exported('Download replenishment plan CSV')
    expected_plan=plan.set_index('SKU').sort_index()
    assert weekly_csv.Product_Name.equals(expected_plan.Product_Name)
    assert np.allclose(weekly_csv[UNITS],expected_plan[UNITS])

    app.button(key='save_plan_a').click().run()
    saved=app.session_state['plan_a']
    a=saved['plans']
    assert a.Model.eq(POISSON).all()
    assert any('same order quantities' in message.value for message in app.info)
    assert 'Replace Plan A' in app.button(key='save_plan_a').label
    assert lp.call_count==count
    default_summary=comparison_summary(app.session_state.applied_simulation['result'],e.BASELINE)
    assert '$2,284.11 lower' in default_summary and '15.77 more' in default_summary and '-0.026 percentage points' in default_summary

    # Match an arrival to a separate week with a different recorded quantity, then check missing coverage.
    arrival_records=a[['Week','SKU','Recorded_Order_Units','Simulated_Fulfilled_Units','Simulated_Unmet_Units']]
    pairs=a.loc[a.Order_Allowed].merge(arrival_records,left_on=['Arrival_Week','SKU'],right_on=['Week','SKU'],suffixes=('','_Later'))
    example=pairs.loc[pairs.Recorded_Order_Units_Later.notna() & pairs.Recorded_Order_Units.ne(pairs.Recorded_Order_Units_Later)].iloc[0]
    decision,actual=sku_details(example.SKU,example.Week,{'Poisson':a})
    raw=e.raw.loc[e.raw.product_id.eq(example.SKU)&e.raw.forecast_week.eq(example.Arrival_Week)].iloc[0]
    assert actual.loc['Recorded order units','Poisson']==f'{raw.actual_order_qty:,.2f}'
    assert actual.loc['Simulated fulfilled units','Poisson']==f'{example.Simulated_Fulfilled_Units_Later:,.2f}'
    assert actual.loc['Simulated unfilled units','Poisson']==f'{example.Simulated_Unmet_Units_Later:,.2f}'
    assert decision.loc['Recommended order (units)','Poisson']==f'{example[UNITS]:,.2f}'
    missing=pairs.loc[pairs.Recorded_Order_Units_Later.isna()].iloc[0]
    assert 'No recorded quantity' in sku_details(missing.SKU,missing.Week,{'Poisson':a})[1].iloc[0,0]
    assert 'outside the replay' in sku_details(example.SKU,e.END,{'Poisson':a})[1].iloc[0,0]

    # Draft edits never change B. Apply changes each week's LP and keeps the saved A fixed.
    app.number_input(key='budget_multiplier').set_value(.75).run()
    assert app.session_state.applied_simulation['parameters'][4]==1.25 and lp.call_count==count
    app.button[0].click().run()
    assert not app.exception and not app.error
    assert lp.call_count>count
    count=lp.call_count
    updated=app.session_state.applied_simulation
    assert updated['parameters'][4]==.75 and app.session_state['plan_a']['parameters'][4]==1.25
    b=updated['plans'].loc[updated['plans'].Model.eq(POISSON)]
    assert b[SPEND].sum()<a[SPEND].sum()
    week=e.weeks[e.sim_weeks[4]]
    app.selectbox(key='compare_week').set_value(week).run()
    wa,wb=a.loc[a.Week.eq(week)],b.loc[b.Week.eq(week)]
    diff=sku_changes(wa,wb.iloc[::-1]).set_index('SKU')
    expected=wb.set_index('SKU')[UNITS]-wa.set_index('SKU')[UNITS]
    assert np.allclose(diff['Change in units'].sort_index(),expected.sort_index())
    assert np.isclose(diff['Change in spend'].sum(),wb[SPEND].sum()-wa[SPEND].sum())
    shown=app.dataframe[1].value.set_index('SKU')
    assert {'Product name','A units','B units','Change in units'}<=set(shown)
    assert shown.index.to_list()==diff.loc[diff['Change in units'].abs().gt(1e-6)].index.to_list()
    compared_csv=exported('Download weekly plan comparison CSV')
    assert compared_csv['Product name'].equals(diff['Product name'].sort_index())
    assert np.allclose(compared_csv['Change in units'],expected.sort_index())
    app.radio[0].set_value('Maximize Fill Rate').run()
    assert lp.call_count==count and app.selectbox(key='compare_week').value==week
    assert app.session_state['plan_a']['plans'].equals(a)
    app.button(key='save_plan_a').click().run()
    assert app.session_state['plan_a']['parameters']==updated['parameters']
    assert any('same order quantities' in item.value for item in app.info)
    app.button(key='clear_plan_a').click().run()
    assert 'plan_a' not in app.session_state and lp.call_count==count
print('PASS: latest eligible default, closed weeks, SKU names and arrival outcomes, dynamic cost/service summary, saved A/B plans, budget changes and weekly SKU deltas.')
