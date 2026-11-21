# Inventory Model Advisor

For a side-by-side comparison of the original dashboard and the weekly planning update, see the [version history](CHANGELOG.md).

The DSO 585 dashboard replays 26 weeks of DataCo replenishment decisions. The top of the page shows overall performance and a Poisson versus four-week average summary. Under **Weekly replenishment**, select a SKU to inspect its order and the recorded and simulated outcomes for its arrival week. The table and CSV include both the SKU and product name.

Under **Compare plans A / B**, save the current applied settings as Plan A, edit a business input and click **Apply Changes** for Plan B. Both use Poisson forecasts. The first table compares 26-week results. The selected-week tables show the purchasing budget, order totals and per-SKU changes for that week. Plan A lasts for the current browser session.

**Online dashboard:** [Inventory Model Advisor](https://inventory-model-advisor.streamlit.app/). **Source repository:** [hiokeigu/inventory-model-advisor](https://github.com/hiokeigu/inventory-model-advisor). Deployed from `main`, entrypoint `app.py`, Python 3.14. `http://127.0.0.1:8501` remains local-only. Read [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md) for ownership details and [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) before changing methodology.

## Run locally

Use Python **3.14** (the tested runtime), then open a terminal in this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, activate with `.venv\Scripts\Activate.ps1`; use `py -3.14 -m venv .venv` if appropriate. Open the URL printed by Streamlit. Keep the terminal running; Ctrl+C stops the service. If port 8501 is occupied, add `--server.port 8502`.

No Colab runtime, Google Drive mount, account credentials, model retraining, or external data downloads are needed. All runtime data are included. Paths resolve relative to `engine.py`; launching from another working directory is supported, but launch from this root to load the theme configuration automatically.

## Files to keep together

```text
app.py                         UI, unit controls, cached results, objective selection
engine.py                      Data validation, forecasts, LP and simulation
comparison_table.py            Client-side header sorting and model highlighting
plan_views.py                  Weekly SKU details and Poisson plan comparisons
data/
  demand_dataset_A.csv         Recorded SKU-week demand
  selected_six_model_predictions.csv  Fixed forecasts and selected windows
  dataco_order_fields.csv.gz   Only the five raw DataCo fields actually used
.streamlit/config.toml         Theme (cream/sage)
requirements.txt               Four pinned runtime dependencies
DATA_MANIFEST.json             Dataset hashes and provenance
verify*.py                     Reproducibility and interaction checks
PROJECT_HANDOFF.md             Methodology, ownership and maintenance guide
DEPLOYMENT_STATUS.md           Deployment blockers and handover checklist
VERIFICATION_REPORT.json       Results of release checks
```

The gzip extract preserves all 180,519 raw order rows and their five selected fields; unused customer and contact fields are excluded. The original raw dataset is not required. See the manifest for exact hashes. Confirm the source DataCo redistribution terms before making the data publicly downloadable; no dataset license is invented or granted by this package.

## Verify before shipping

```sh
python verify.py
python verify_ui.py
python verify_replenishment.py
python verify_package.py
```

These checks run real LP simulations. Expected defaults: annual holding 15%, stockout penalty 50% of SKU gross profit, current inventory 1× historical demand, lead time 1 week, budget 1.25× reference cost. Poisson Regression has operating cost **$17,734.61**, fill rate **99.024338876%** (displayed 99.02%), ending inventory value **$145,873.51**. Balanced retains both Poisson and the four-week baseline. These values are regression checks, never application result substitutes.

## Transfer to GitHub

1. Create a repository under the teammate/team account. Start private while confirming dataset redistribution rights. Grant the teammate maintain/write access through GitHub.
2. Put this folder's **contents at the repository root**, including `.streamlit/`, `.gitignore`, `data/` and the gzip file. Do not upload the ZIP as the application source, `.venv/`, caches, or the parent workspace.
3. Using Git from this folder (replace `YOUR_REPOSITORY_URL` with the actual repository URL):

```sh
git init -b main
git add .
git commit -m "Add portable Inventory Model Advisor"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

GitHub Desktop is an equivalent option. No large-file storage or absolute local paths are required for the bundled files. Review the staged files before pushing.

## Deploy on Streamlit Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) with the account that will maintain the app. The account owner must complete any terms/authorization prompts.
2. Give Community Cloud access to the chosen GitHub repository. Switch to the workspace matching its owner.
3. Choose **Create app → Yup, I have an app**. Select the repository, `main`, and **`app.py`** as the entrypoint.
4. In **Advanced settings**, select **Python 3.14**. This project pins dependencies tested on that version. If the platform does not offer it, test a supported version in a fresh environment before changing dependencies; do not silently use a different interpreter.
5. No secrets are needed for this bundled-data demo. Deploy and inspect the build logs.
6. Open the assigned `https://…streamlit.app` URL and verify defaults, each objective, Apply Changes, table sorting, and an earlier week's replenishment CSV. Test in a separate signed-out browser if public access is intended. Record the actual repository/app URLs in DEPLOYMENT_STATUS.md only after verification.

Official references: [deployment configuration](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [app maintenance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app). Instructions checked November 19, 2026; platform availability can change.

## Update and maintain

Work on a branch, run the four checks, review changed results, then merge to the deployed branch. Community Cloud redeploys when that branch changes; dependency changes trigger installation. Inspect **Manage app → logs** if deployment fails; use Reboot after correcting the cause. Keep the four dependency pins and Python version synchronized. The UI uses some Streamlit CSS selectors, so visually review the dashboard after upgrades.

## Troubleshooting

| Symptom | Action |
|---|---|
| Local URL unavailable | Start Streamlit and keep its terminal open; localhost is not a public deployment. |
| Missing data / gzip read error | Restore all three files under `data/`; compare DATA_MANIFEST hashes; do not substitute an HTML download page for a CSV. |
| Missing package / unsupported widget | Use the activated Python 3.14 environment and install this requirements.txt; check `python --version` and `python -m pip check`. |
| `evaluate()` argument mismatch | Deploy app.py and engine.py from the same release; reboot the service. The versioned backend loader avoids stale imported modules and passes named options. |
| Assertions or LP failure | Check data schema, prediction coverage, nonnegative inputs, units and LP error message. Keep validation enabled; never replace failed results with example numbers. |
| Input edit does not change KPIs | Click Apply Changes. Objective changes intentionally reuse the most recently applied operating assumptions. |
| A selected week is closed to orders | Orders must arrive by September 25, 2017. The weekly view opens on the latest eligible order week for the applied lead time. Later weeks remain available for review. |
| Cloud app slow or resource-limited | Inspect logs, reduce concurrent heavy evaluations or choose suitable hosting. Results cache is bounded to 32 parameter combinations per process. |

## Handoff acceptance

The teammate should run the package locally, verify defaults, obtain repository write access from hiokeigu, and review the data/license limitations. The app is deployed; future updates to the deployed main branch propagate through Community Cloud. Repository visibility does not grant the teammate write access: add their GitHub username through Settings → Collaborators, and verify their Cloud maintenance access separately.
