"""Verify captured decisions against LP outputs and dashboard selection."""
from unittest.mock import patch
import numpy as np
import engine as e
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

with patch('scipy.optimize.linprog',wraps=linprog) as lp:
    app=AppTest.from_file('app.py',default_timeout=120).run()
    assert not app.exception and not app.error
    count=lp.call_count
    assert app.metric[3].value=='0.00'
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
print('PASS: latest-week default; week/candidate changes reuse decisions; table and summary totals match selected model/week.')
