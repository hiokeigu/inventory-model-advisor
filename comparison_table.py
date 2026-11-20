"""Small client-side sortable table; no server callbacks or table menus."""
from html import escape
import streamlit as st


def render_comparison(table, recommended):
    headers = ''.join(
        f'<th scope="col" aria-sort="none"><button type="button" data-column="{i}">{escape(col)} <span></span></button></th>'
        for i, col in enumerate(table.columns)
    )
    rows = []
    for _, row in table.iterrows():
        cells = []
        for col in table.columns:
            value = row[col]
            if col == 'Model':
                display, sort_value = escape(str(value)), escape(str(value), quote=True)
            elif col in ('Total Operating Cost', 'Ending Inventory Value'):
                display, sort_value = f'${value:,.2f}', str(float(value))
            elif col == 'Fill Rate':
                display, sort_value = f'{value:.2%}', str(float(value))
            else:
                display, sort_value = ('Yes' if value else '—'), str(int(value))
            cells.append(f'<td data-value="{sort_value}">{display}</td>')
        highlight = 'recommended' if row['Model'] in recommended else ''
        rows.append(f'<tr class="{highlight}">' + ''.join(cells) + '</tr>')
    markup = """<!doctype html><html><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:#f8f6ef;color:#293c30;font:14px system-ui,sans-serif}
    .wrap{overflow-x:auto;border:1px solid #d9dfd2;border-radius:10px}
    table{border-collapse:collapse;width:100%;text-align:right;background:#fffdf7}
    th,td{padding:12px 10px;border-bottom:1px solid #e3e6dc;white-space:nowrap}
    th{background:#eeeee4;font-weight:600}th:first-child,td:first-child{text-align:left}
    th button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:inherit;width:100%}
    th button:focus-visible{outline:2px solid #627b5a;outline-offset:4px}
    th span{font-size:11px;color:#627b5a}tr:last-child td{border:0}
    tr.recommended td{background:#e6eddf;color:#304c38}
    </style></head><body><div class="wrap"><table><thead><tr>""" + headers + """</tr></thead><tbody>""" + ''.join(rows) + """</tbody></table></div>
    <script>
    const table=document.querySelector('table');
    table.querySelectorAll('th button').forEach(button=>{
      button.addEventListener('click',()=>{
        const index=Number(button.dataset.column), th=button.parentElement;
        const ascending=th.getAttribute('aria-sort')!=='ascending';
        table.querySelectorAll('th').forEach(h=>{h.setAttribute('aria-sort','none');h.querySelector('span').textContent='';});
        th.setAttribute('aria-sort',ascending?'ascending':'descending');
        button.querySelector('span').textContent=ascending?'▲':'▼';
        const rows=Array.from(table.tBodies[0].rows);
        rows.sort((a,b)=>{
          const x=a.cells[index].dataset.value,y=b.cells[index].dataset.value;
          const order=index===0?x.localeCompare(y):Number(x)-Number(y);
          return ascending?order:-order;
        });
        rows.forEach(row=>table.tBodies[0].appendChild(row));
      });
    });
    </script></body></html>"""
    st.iframe(markup, height=365, alt='Sortable model comparison')
