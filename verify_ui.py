"""Run with .venv/bin/python verify_ui.py from this folder."""
from unittest.mock import patch
from datetime import timedelta
from streamlit.testing.v1 import AppTest
from scipy.optimize import linprog

with patch('scipy.optimize.linprog', wraps=linprog) as optimizer:
    app=AppTest.from_file('app.py', default_timeout=120).run()
    def healthy():
        assert not app.exception, app.exception
        assert not app.error, [x.value for x in app.error]
        assert len(app.metric)==5
    healthy()
    assert app.metric[0].value=='$17,734.61'
    assert app.metric[1].value=='99.02%'
    assert app.selectbox(key='lead_time_weekly').options==['1 week','2 weeks','3 weeks']
    last_week=app.session_state.applied_simulation['plans'].Week.max()
    count=optimizer.call_count
    for objective in ['Maximize Fill Rate','Balanced (Pareto)','Minimize Total Operating Cost']:
        app.radio[0].set_value(objective).run()
        healthy()
        assert optimizer.call_count==count
    app.button[0].click().run()
    assert optimizer.call_count==count, 'Unchanged Apply must not optimize'
    for lead in [2,3,1]:
        before=optimizer.call_count
        app.selectbox(key='lead_time_weekly').set_value(lead).run()
        assert optimizer.call_count==before
        app.button[0].click().run()
        healthy()
        assert app.session_state.applied_simulation['parameters'][3]==lead
        assert app.selectbox(key='plan_week').value==last_week-timedelta(weeks=lead)
    # Each non-default unit mode, independently applied.
    for key, value, position in [
        ('holding_unit_tabs','$/Unit/Week',5),
        ('penalty_unit_tabs','$/Unit',6),
        ('budget_unit_tabs','$/Week',7),
    ]:
        before=optimizer.call_count
        app.session_state[key]=value
        app.run()
        healthy()
        assert optimizer.call_count==before
        app.button[0].click().run()
        healthy()
        assert optimizer.call_count>before
        assert app.session_state.applied_simulation['parameters'][position] is not None
    before=optimizer.call_count
    app.number_input(key='current_inventory').set_value(1.5).run()
    assert optimizer.call_count==before
    app.button[0].click().run()
    healthy()
    assert optimizer.call_count>before
    assert app.session_state.applied_simulation['parameters'][2]==1.5
print('PASS: baseline, all three weekly lead times, alternative unit modes, inventory multiplier, immediate objectives, and Apply-only optimization.')
