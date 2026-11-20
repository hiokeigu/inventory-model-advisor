# Dashboard version history

## v1.1 (proposed) — Compare replenishment plans

| Task | v1.0 | v1.1 |
| --- | --- | --- |
| Compare budgets or lead times | The dashboard shows model results for one set of business inputs at a time. | Save Plan A in the browser session, then apply different inputs for Plan B. Both use Poisson forecasts. Compare operating cost, fill rate, unfilled units, purchase spend and ending inventory value over 26 weeks. |
| Choose an order week | The weekly plan opens on the last week of the replay, September 25, 2017. | The weekly plan opens on the latest week when an order placed that week can arrive by September 25. With a one-week lead time it opens on September 18. The selected week's orders appear separately from the 26-week results. |
| Review and export SKU orders | The weekly table and CSV identify products by SKU. | Both include SKU and product name. Select a product to inspect the stock and forecast used at order time, then expand its arrival-week outcome. The A/B view and its CSV show changes in order units and purchase spend by SKU. |
| Explain the cost and service trade-off | Users read each model's cost and fill rate from the comparison table. | A summary quantifies how Poisson differs from the four-week moving average in operating cost, unfilled units and fill-rate percentage points under the applied inputs. |

## v1.0 — Original team dashboard

The original dashboard compares seven forecasting methods under editable operating assumptions and produces a weekly SKU replenishment plan from the 26-week DataCo replay. The baseline for this comparison is commit `b2b4f8d`. [Browse the original source files](https://github.com/hiokeigu/inventory-model-advisor/tree/b2b4f8d1416f3a64617d009a9179bca38fd378ba)
