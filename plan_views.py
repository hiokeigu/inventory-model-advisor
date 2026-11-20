"""Weekly inventory decisions and comparisons between two Poisson replenishment plans."""

import pandas as pd
import streamlit as st


POISSON = 'Poisson Regression'
UNITS = 'Recommended_Order_Quantity'
SPEND = 'Estimated_Purchase_Cost'
PLAN_COLUMNS = {
    'SKU': 'SKU', 'Product_Name': 'Product name', UNITS: 'Order units',
    SPEND: 'Purchase spend', 'Starting_Inventory': 'Starting inventory',
    'Forecast_Demand': 'Forecast units',
}


def comparison_summary(results, baseline):
    indexed = results.set_index('Model')
    poisson, reference = indexed.loc[POISSON], indexed.loc[baseline]
    cost = round(poisson.Total_Simulated_Cost - reference.Total_Simulated_Cost, 2)
    units = round(poisson.Unmet_Demand_Units - reference.Unmet_Demand_Units, 2)
    rate = round(100 * (poisson.Fill_Rate - reference.Fill_Rate), 3)
    cost_text = 'the same' if cost == 0 else f'${abs(cost):,.2f} {"lower" if cost < 0 else "higher"}'
    units_text = 'the same number of' if units == 0 else f'{abs(units):,.2f} {"fewer" if units < 0 else "more"}'
    rate_text = f'{rate:+.3f}' if rate else '0.000'
    return (f"Compared with the four-week average, Poisson’s simulated operating cost was {cost_text}. "
            f"It left {units_text} units unfilled (fill-rate difference {rate_text} percentage points).")


def choose_week(weeks, orderable_weeks, key, label):
    options = sorted(pd.Timestamp(w) for w in weeks)
    latest = max((pd.Timestamp(w) for w in orderable_weeks), default=options[-1])
    default_key = key + '_latest_orderable'
    previous = st.session_state.get(default_key)
    current = st.session_state.get(key)
    # Follow the default when lead time changes. Preserve a deliberately inspected older week.
    if current not in options or (current == previous and latest != previous):
        st.session_state[key] = latest
    st.session_state[default_key] = latest
    return st.selectbox(label, options, key=key,
                        format_func=lambda d: d.strftime('%b %d, %Y'))


def sku_details(sku, week, sources):
    """Use decision-time fields for the order. Reveal the matched arrival-week record separately."""
    decision, outcome = {}, {}
    for label, plans in sources.items():
        product = plans.loc[plans.SKU.eq(sku)].set_index('Week')
        if week not in product.index:
            decision[label] = {'Order week': 'SKU not eligible'}
            outcome[label] = {'Coverage': 'SKU not eligible'}
            continue
        row = product.loc[week]
        arrival = row.Arrival_Week

        def units(column):
            value = row[column]
            return '—' if pd.isna(value) else f'{value:,.2f}'

        decision[label] = {
            'Arrival week': arrival.strftime('%b %d, %Y'),
            'Stock after scheduled receipts': units('Starting_Inventory'),
            'Previously ordered units due by arrival': units('Scheduled_Inbound_Units'),
            'Expected use before arrival': units('Forecast_Use_Before_Arrival'),
            'Projected stock before the new order arrives': units('Projected_Stock_Before_New_Order'),
            'Demand scenarios for the arrival week': (
                f'{units("Arrival_Scenario_Min")} – {units("Arrival_Scenario_Max")}' if row.Order_Allowed else '—'),
            'Recommended order (units)': units(UNITS),
            'Estimated purchase spend': f'${row[SPEND]:,.2f}',
        }
        if not row.Order_Allowed or arrival not in product.index:
            outcome[label] = {'Coverage': 'Arrival outside the replay'}
        elif pd.isna(product.loc[arrival, 'Recorded_Order_Units']):
            outcome[label] = {'Coverage': 'No recorded quantity for this SKU-week'}
        else:
            later = product.loc[arrival]
            outcome[label] = {
                'Arrival week': arrival.strftime('%b %d, %Y'),
                'Recorded order units': f'{later.Recorded_Order_Units:,.2f}',
                'Simulated fulfilled units': f'{later.Simulated_Fulfilled_Units:,.2f}',
                'Simulated unfilled units': f'{later.Simulated_Unmet_Units:,.2f}',
            }
    return pd.DataFrame(decision).fillna('—'), pd.DataFrame(outcome).fillna('—')


def product_table(frame, week, sources, key):
    """Keep SKU as the row identity even when the displayed table is sorted or filtered."""
    config = {
        'SKU': st.column_config.Column('SKU', width=58, pinned=True),
        'Product name': st.column_config.TextColumn('Product name', width=160),
    }
    for col in frame.columns:
        if col not in ('SKU', 'Product name'):
            numeric_format = '$%.2f' if 'spend' in col.lower() else '%.2f'
            config[col] = st.column_config.NumberColumn(col, format=numeric_format)
    event = st.dataframe(frame, hide_index=True, width='stretch', height='auto',
                         column_config=config, on_select='rerun', selection_mode='single-row', key=key)
    selected = event.selection.rows
    if not selected or selected[0] >= len(frame):
        return
    item = frame.iloc[selected[0]]
    st.markdown(f'**SKU {item["SKU"]} · {item["Product name"]}**')
    st.caption(f'Decision on {week:%b %d, %Y}. Projected stock includes previously scheduled arrivals and deducts expected use during lead time.')
    decision, outcome = sku_details(item['SKU'], week, sources)
    st.table(decision)
    with st.expander('What happened in the arrival week?'):
        st.caption('Recorded orders are historical. Fulfillment is simulated using all stock available in the arrival week.')
        st.table(outcome)


def render_weekly_plan(plans, model, parameters):
    st.subheader('Selected-week replenishment')
    st.caption(f'{model} · Historical DataCo order decisions')
    selectable = plans.loc[plans.Order_Allowed, 'Week'].unique()
    week = choose_week(plans.Week.unique(), selectable, 'plan_week', 'Simulation week')
    plan = plans.loc[plans.Week.eq(week)].sort_values([UNITS, 'SKU'], ascending=[False, True])
    spend = plan[SPEND].sum()
    budget = plan.Weekly_Purchasing_Budget.iloc[0]
    assert spend <= budget + 1e-5
    a, b = st.columns(2)
    a.metric('Total Replenishment Units', f'{plan[UNITS].sum():,.2f}')
    b.metric('Estimated Purchase Cost', f'${spend:,.2f}')
    st.caption(rf'Weekly budget \${budget:,.2f} · Unspent \${max(0, budget - spend):,.2f} · Simulated quantities may be fractional.')
    if not plan.Order_Allowed.any():
        st.info('An order placed this week would arrive after the replay ends.')
    st.caption('Select the checkbox beside a SKU to see its stock, forecast and arrival-week outcome.')
    display = plan[list(PLAN_COLUMNS)].rename(columns=PLAN_COLUMNS)
    product_table(display, week, {model: plans}, f'orders_{week:%Y%m%d}_{model}_{hash(parameters)}')
    export = plan.drop(columns=['Recorded_Order_Units', 'Simulated_Fulfilled_Units', 'Simulated_Unmet_Units'])
    export = export.assign(Context='Historical DataCo simulation. Quantities reflect information available at the ordering decision.')
    st.download_button('Download replenishment plan CSV', export.to_csv(index=False),
                       f'replenishment_{week:%Y-%m-%d}_{model.replace(" ", "_")}.csv', 'text/csv')


def settings(parameters):
    carry, penalty, initial, lead, budget, fixed_holding, fixed_penalty, fixed_budget = parameters
    return {
        'Weekly purchasing budget': f'{budget:g}× reference cost' if fixed_budget is None else f'${fixed_budget:,.2f}/week',
        'Holding cost': f'{carry:.2%}/year' if fixed_holding is None else f'${fixed_holding:,.2f}/unit/week',
        'Stockout penalty': f'{penalty:.2%} of gross profit' if fixed_penalty is None else f'${fixed_penalty:,.2f}/unit',
        'Initial stock': f'{initial:g}× historical average',
        'Lead time': f'{lead} week' if lead == 1 else f'{lead} weeks',
    }


def sku_changes(plan_a, plan_b):
    """Compare identical SKU identities for the selected week, regardless of table order."""
    columns = ['Product_Name', UNITS, SPEND]
    a = plan_a.set_index('SKU', verify_integrity=True)[columns]
    b = plan_b.set_index('SKU', verify_integrity=True)[columns]
    joint = a.join(b, how='outer', lsuffix='_A', rsuffix='_B', validate='one_to_one')
    changes = pd.DataFrame({
        'Product name': joint.Product_Name_A.combine_first(joint.Product_Name_B),
        'Change in units': joint[UNITS + '_B'] - joint[UNITS + '_A'],
        'A units': joint[UNITS + '_A'], 'B units': joint[UNITS + '_B'],
        'A spend': joint[SPEND + '_A'], 'B spend': joint[SPEND + '_B'],
        'Change in spend': joint[SPEND + '_B'] - joint[SPEND + '_A'],
    })
    return changes.sort_values('Change in units', key=lambda s: s.abs(), ascending=False, kind='stable').reset_index()


def compare_table(measures):
    records = []
    for label, a, b, fmt in measures:
        decimals = 3 if fmt == 'rate' else 2
        factor = 100 if fmt == 'rate' else 1
        prefix = '$' if fmt == 'money' else ''
        suffix = '%' if fmt == 'rate' else ''
        change = round((b - a) * factor, decimals)
        sign = '+' if change > 0 else '−' if change < 0 else ''
        records.append({
            'Measure': label,
            'Plan A': f'{prefix}{a * factor:,.{decimals}f}{suffix}',
            'Plan B': f'{prefix}{b * factor:,.{decimals}f}{suffix}',
            'Change (B − A)': f'{sign}{prefix}{abs(change):,.{decimals}f}{" pp" if fmt == "rate" else ""}',
        })
    st.table(pd.DataFrame(records).set_index('Measure'))


def render_plan_comparison(applied):
    st.subheader('Compare replenishment plans')
    st.caption('Both plans use Poisson Regression. Plan A is saved in this session. Plan B uses the last applied settings for all 26 weeks.')
    saved = st.session_state.get('plan_a')
    if saved is not None and saved['revision'] != applied['revision']:
        del st.session_state['plan_a']
        saved = None
    current_metric = applied['result'].set_index('Model').loc[POISSON]
    current_plans = applied['plans'].loc[applied['plans'].Model.eq(POISSON)]
    def save_current():
        st.session_state['plan_a'] = {
            'revision': applied['revision'], 'parameters': applied['parameters'],
            'metrics': current_metric.copy(), 'plans': current_plans.copy(),
        }
    save, clear = st.columns(2)
    save.button('Save current settings as Plan A' if saved is None else 'Replace Plan A with current settings',
                key='save_plan_a', on_click=save_current)
    if saved is None:
        st.info('Save a starting plan, then change a business input and select Apply Changes to compare.')
        return
    clear.button('Clear Plan A', key='clear_plan_a', on_click=st.session_state.pop, args=('plan_a', None))

    assumptions = pd.DataFrame({'Plan A': settings(saved['parameters']), 'Plan B': settings(applied['parameters'])})
    different = assumptions['Plan A'].ne(assumptions['Plan B'])
    if different.any():
        st.table(assumptions.loc[different])
    else:
        st.caption('The applied settings are identical. Edit an input and select Apply Changes to create a different Plan B.')
    if different[['Holding cost', 'Stockout penalty']].any():
        st.caption('Operating cost in each plan uses its own unit charges. The cost difference includes that change in valuation.')

    a, b = saved['metrics'], current_metric
    full_a, full_b = saved['plans'], current_plans
    st.markdown('#### 26-week performance')
    compare_table([
        ('Simulated operating cost', a.Total_Simulated_Cost, b.Total_Simulated_Cost, 'money'),
        ('Fill rate', a.Fill_Rate, b.Fill_Rate, 'rate'),
        ('Unfilled units', a.Unmet_Demand_Units, b.Unmet_Demand_Units, 'units'),
        ('Purchase spend', full_a[SPEND].sum(), full_b[SPEND].sum(), 'money'),
        ('Ending inventory value', a.Final_Inventory_Value, b.Final_Inventory_Value, 'money'),
    ])
    st.markdown('#### Selected-week orders')
    orderable = set(full_a.loc[full_a.Order_Allowed, 'Week']) & set(full_b.loc[full_b.Order_Allowed, 'Week'])
    week = choose_week(full_b.Week.unique(), orderable, 'compare_week', 'Order week to compare')
    wa = full_a.loc[full_a.Week.eq(week)]
    wb = full_b.loc[full_b.Week.eq(week)]
    compare_table([
        ('Weekly budget', wa.Weekly_Purchasing_Budget.iloc[0], wb.Weekly_Purchasing_Budget.iloc[0], 'money'),
        ('Order units', wa[UNITS].sum(), wb[UNITS].sum(), 'units'),
        ('Purchase spend', wa[SPEND].sum(), wb[SPEND].sum(), 'money'),
    ])
    closed = [label for label, frame in [('A', wa), ('B', wb)] if not frame.Order_Allowed.any()]
    if closed:
        st.caption(f'Arrival is outside the replay for plan {" and ".join(closed)}.')
    changes = sku_changes(wa, wb)
    mask = changes['Change in units'].abs().gt(1e-6) | changes['Change in units'].isna()
    count = int(mask.sum())
    if count:
        st.caption(f'{count} SKUs have different orders. Largest changes in units appear first. Select a SKU’s checkbox for details.')
    else:
        st.info('The two plans have the same order quantities for this week.')
    all_rows = st.checkbox('Include unchanged SKUs', key='include_unchanged')
    visible = changes if all_rows else changes.loc[mask]
    if not visible.empty:
        identity = hash((saved['parameters'], applied['parameters'], all_rows))
        product_table(visible, week, {'Plan A': full_a, 'Plan B': full_b}, f'changes_{week:%Y%m%d}_{identity}')
    export = changes.assign(Week=week, Model=POISSON,
                            Plan_A_Weekly_Budget=wa.Weekly_Purchasing_Budget.iloc[0],
                            Plan_B_Weekly_Budget=wb.Weekly_Purchasing_Budget.iloc[0])
    st.download_button('Download weekly plan comparison CSV', export.to_csv(index=False),
                       f'poisson_plan_comparison_{week:%Y-%m-%d}.csv', 'text/csv')
