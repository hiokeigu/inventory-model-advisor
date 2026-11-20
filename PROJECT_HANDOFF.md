# Project Handoff — Inventory Model Advisor

Prepared November 19, 2026 for the DSO 585 Capstone team. This guide describes the packaged implementation, not a proposed future product. Original working files were preserved separately.

## A. Project Overview

The advisor compares fixed demand forecasts through a shared inventory optimization and simulation process. Business users choose an objective and operating conditions; the application identifies suitable cost/service strategies and exposes the historical replenishment decisions that generated them.

It is a retrospective DataCo demonstration for April 3–September 25, 2017 (26 weekly decisions), with forecast-error warmup starting February 6. It does not predict today's inventory or place purchase orders.

## B. Dashboard Features

Implemented:

- **Business Objectives:** Minimize Total Operating Cost, Maximize Fill Rate, Balanced (Pareto). Changing the objective immediately selects from the last applied simulation, without another LP run.
- **Holding Cost:** annual percentage of estimated SKU purchase cost, or uniform dollars per unit per week.
- **Stockout Penalty:** percentage of estimated SKU unit gross profit, or uniform dollars per unmet unit.
- **Current Inventory:** historical average weekly demand × multiplier; an initialization assumption, not observed current stock.
- **Lead Time:** 1, 2 or 3 whole weeks. The dashboard has no daily input or daily rounding.
- **Purchasing Budget:** multiplier of the existing trailing-four-calendar-week cost reference, or fixed dollars per week.
- **Apply Changes:** operating edits remain drafts; submitting changed values obtains inventory simulation results from real LP calculations or an identical-input cache. Repeated unchanged submissions do not recalculate. Objective and plan-week changes do not apply drafts.
- **Recommendations and KPIs:** operating cost, fill rate and ending inventory value correspond to the selected model; exact ties are retained. In Pareto mode, inspect any efficient candidate with the candidate selector.
- **Model Comparison:** seven methods; currency and percentage formatting; recommended candidates highlighted; header-only ascending/descending sorting performed in browser JavaScript without server callbacks.
- **Replenishment Plan:** selected historical week, total order units and purchase cost, SKU starting stock/forecast/order quantities/costs, and a CSV. It follows the currently inspected recommendation and defaults to the final evaluated week. Zero orders at the end of the horizon are expected.
- **Exports:** seven-model comparison and selected model/week replenishment details. CSVs retain numeric precision; UI rounding is only presentation.
- **Notes:** summary table, limitations, secondary Technical Details and source Colab link.

Not implemented: company-data uploads, forecast fitting/retraining, live stock or procurement integration, SKU-specific manual cost/penalty inputs, daily simulation, production access control, or automatic monitoring. These remain future work.

## C. Forecasting and Optimization Methodology

### Forecasts

Six trained models are XGBoost, LightGBM, Ridge, Lasso, Linear Regression and Poisson Regression. Their precomputed predictions, selected windows and training cutoff dates come from `selected_six_model_predictions.csv`; no model libraries or fitting are needed at runtime. Technical Details displays each actual window. The seventh method is a four-calendar-week moving average excluding the current week. Its mean uses available observations; if the window has none, the inherited replenishment forecast fallback is zero. This does not establish zero true demand.

The loader verifies common SKU/week coverage, matching recorded actual quantities, one selected window per model, finite predictions, and `train_end < forecast_week`. Missing model rows are forward-filled with the last prediction, with a zero fallback before any prediction.

### Uncertainty scenarios

For a weekly decision, standardized residuals use only historical actual/forecast pairs known before that decision: `(actual - forecast) / sqrt(max(forecast, 1))`. They are pooled across available SKU/week pairs for each model. With at least 30 residuals, 41 empirical quantiles create nonnegative demand scenarios around the current forecast. Otherwise the LP uses the point forecast. This is an empirical model-specific buffer, not a guarantee of calibrated probabilities or an independent uncertainty model per SKU.

### LP and inventory flow

`solve_order_lp(base, scen, h, p, unit_cost, budget)` minimizes expected remaining-inventory holding cost plus unmet-demand penalty over scenarios. Continuous nonnegative variables represent order quantity and scenario overage/shortage. `sum(order_qty × SKU purchase cost) <= weekly budget`. SciPy HiGHS solves the sparse LP and raises on failure.

At week start, newly eligible SKUs receive their assumed initial stock, scheduled orders arrive, and the model chooses replenishment. Only SKUs observed in a completed historical week are eligible. The weekly simulation then serves recorded demand, loses unmet demand (no backlog), carries remaining stock forward, and charges holding cost. No discontinuation rule or automatic write-off is used. Stock conservation and budget assertions are checked.

For positive lead times, current forecasts approximate demand through lead time and the arrival week; scheduled pipeline quantities enter the base-stock approximation. Forecasts are not refitted for true multi-step horizons. Orders arriving after the evaluation window are suppressed.

### Costs and selection

In percentage mode, weekly holding cost per SKU unit is `estimated purchase cost × annual holding fraction / 52`. Stockout penalty per unmet unit is `historical selling price × 0.3318 × penalty fraction`. Fixed-dollar modes directly supply weekly holding cost and per-unmet-unit penalty uniformly across SKUs. They feed the same LP coefficients and realized simulation accounting.

Total Operating Cost is Holding Cost + Lost-sales Penalty. Purchase spending limits orders but is not added again as a duplicate operating expense. Ending Inventory Value is remaining simulated units × estimated purchase cost, reported as an asset/capital commitment rather than an automatic loss. This is not a complete profit model.

Cost selection retains every exact minimum; service selection retains every exact maximum of unrounded fill rate. Balanced retains all non-dominated cost/fill pairs, including the baseline. Another method dominates only if cost is no greater and fill rate no lower, with at least one strict improvement. Equal pairs both remain. No weighted score or mandatory unique winner exists.

## D. Data and Assumptions

| File | Role |
|---|---|
| `data/demand_dataset_A.csv` | Recorded weekly quantities keyed by product_id and forecast_week. |
| `data/selected_six_model_predictions.csv` | Six fixed prediction series, actual quantities, selected Window, train_end. |
| `data/dataco_order_fields.csv.gz` | All raw-order rows projected to Product Card Id, order date (DateOrders), Order Item Product Price, Order Item Quantity and Sales. Used for historical price medians and source cross-checks. |
| `DATA_MANIFEST.json` | Exact input hashes/sizes, projection provenance and original-source hashes. |

The gzip projection retains the required source values and all rows while excluding customer and contact fields. It is not an invented or synthetic replacement. Its contents are sufficient without the original full raw CSV. Dataset A differs from the unfiltered raw aggregation in 1,829 rows; the supplied Dataset A is intentionally retained and upstream filtering remains unverified. Local CSV identity against current cloud files and raw-data redistribution terms have not been independently established.

**33.18% gross margin** is an assumed benchmark inherited from the notebook, not an observed margin for every SKU. SKU purchase cost is historical median selling price × 0.6682; unit gross profit is selling price × 0.3318. The price identity (Sales = unit price × quantity) is validated. Price medians use observations before simulation start or the new SKU's first eligible entry, then remain fixed.

Defaults are 15% annual holding, 50% gross-profit penalty, inventory multiplier 1, one-week lead time and budget multiplier 1.25. Initial stock uses a historical calendar-week mean; initialization and budget treat missing quantities as zero contributions. The budget reference uses the previous four calendar weeks' average quantities valued at SKU costs across eligible SKUs. It is a reference purchasing cost, not actual observed purchasing expense. Missing records do not prove zero demand.

The displayed order table uses stock after scheduled receipts and initialization, before the current order/demand. Forecast Demand is the model forecast, not a claim that it alone equals the buffered LP scenario. The order quantity comes directly from the saved LP decision array. Only eligible SKU rows are shown, including zero-order rows; continuous quantities are intentional. The plan CSV includes model, week, unit costs, weekly budget, horizon/order eligibility and historical context.

## E. Code Structure and Change Locations

| Component | Responsibility / where to edit |
|---|---|
| `app.py` | Layout/CSS, input widgets and unit labels, session state, objective selection, KPI formatting, CSV downloads and plan rendering. |
| `unit_switch()` | Segmented unit controls. Preserve conversions and named parameter mapping when changing options. |
| `calculate()` | Bounded cached inventory evaluation; never performs forecasting fits. |
| `load_backend()` / `ENGINE_REVISION` | Source-hash versioned engine loading. Prevents retaining an old evaluate signature after source changes; revision invalidates stale results. |
| `engine.py` top-level setup | Required-file checks, input schema/coverage, matrices, selected model windows, historical prices, baseline, initial inventory, RUN_RATE. |
| `matrix()` | Aligns SKU/week data to the common evaluation calendar. |
| `residual_quantiles()` | Historical standardized residual buffer; avoid future-information leakage. |
| `solve_order_lp()` | Sparse budget-constrained optimizer and failure handling. |
| `simulate()` | Receipts, eligibility, orders, demand/service, costs, inventory conservation and optional decision_log capture. |
| `evaluate()` | All seven method evaluations, Pareto flags; optionally returns `(results, plans)` when include_plans=True. Default remains a results DataFrame. |
| `comparison_table.py` | Escaped HTML, numeric client-side sorting and highlighting; no simulation callbacks. |
| `.streamlit/config.toml` | Theme tokens. |
| `verify.py` | Source-baseline equivalence and parameter sensitivity. |
| `verify_ui.py` | Input/unit/lead-time behavior, objectives and optimizer call counts. |
| `verify_replenishment.py` | Exact agreement of logged SKU quantities and costs with LP order arrays; candidate/week selection tests. |
| `verify_package.py` | Bundled-file integrity, allowed raw fields and absence of machine-specific source paths. |

To add/replace forecasting models, obtain properly validated out-of-sample predictions and update MODELS, prediction coverage and window checks together. Changing the recommendation code alone does not add a trained model. Current training notebooks are references via the Colab link, not bundled training infrastructure.

### Maintenance rules

Preserve raw precision for ranking, cost accounting and CSVs. UI formats do not determine winners. Keep identical data/economics/eligibility across compared models. Every UI unit option must map consistently into both LP coefficients and realized accounting. Preserve include_plans handling and use the inspected row's model for replenishment; do not derive a second order formula in the UI.

An operating edit causes a Streamlit render but no inventory optimization until Apply. Objective, week, and candidate controls use saved results. Table sorting is entirely browser-side. Unchanged Apply is a no-op; identical historical combinations may use cache. Do not introduce implicit application of drafts during selection changes.

## F. Known Limitations and Future Improvements

The comparison is retrospective, based on recorded orders rather than unconstrained demand, with unknown missing weeks and unobserved lost sales. Selected forecasting windows may have been chosen using periods overlapping evaluation, creating potential selection bias. Fixed outputs cannot adapt to new companies or market changes. Historical prices and assumed margin, initial stock and budgets are estimates, not measured inventory operations.

The simulation is weekly, uses continuous order quantities, a myopic LP and a lead-time forecast approximation. It omits pack sizes, integer constraints, supplier minimums, order fees, storage capacity, backorders, live lead-time uncertainty and many accounting costs. The finite horizon suppresses late replenishment and affects final inventory. Equal or tiny differences in performance should not be overstated as economic certainty.

Future work: independently validate Dataset A preparation and untouched test performance; add a governed company-data pipeline and real SKU inventory/economics; train multi-step forecasts; add operational constraints; validate uncertainty calibration; benchmark cloud resources and concurrency; introduce authentication if necessary. None of these is implied to exist today.

## Deployment and ownership

Live dashboard: https://inventory-model-advisor.streamlit.app/

Repository: https://github.com/hiokeigu/inventory-model-advisor (owner: hiokeigu; deployed branch: main; entrypoint: app.py; Python 3.14).

The repository and Community Cloud deployment are established. The owner approved Streamlit's GitHub connection. No application secrets are required. Add the teammate's GitHub username through repository Settings → Collaborators, then verify their ability to view Cloud logs and maintain deployment. Public read access alone does not grant write access. Follow README for local execution, deployment updates and troubleshooting. Data redistribution rights remain unverified; no dataset license is granted by this repository. See VERIFICATION_REPORT.json for release tests and reference equivalence.

The working local copy has not been overwritten. The portable handoff removes runtime-only debug prints and IPython, uses a compressed five-field projection, bounds the result cache, and migrates deprecated rendering calls to the pinned Streamlit APIs. Forecasting arrays, LP objective/constraints, simulation flow and selection rules are preserved and verified against the original.
