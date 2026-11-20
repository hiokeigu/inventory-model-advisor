# Deployment Status and Ownership

Status: deployed on Streamlit Community Cloud.

- Dashboard: https://inventory-model-advisor.streamlit.app/
- Direct app view (fallback if the Cloud wrapper keeps loading): https://inventory-model-advisor.streamlit.app/~/+/
- Repository: https://github.com/hiokeigu/inventory-model-advisor
- Repository owner / Cloud workspace: hiokeigu
- Visibility: public repository; public app URL
- Deployed branch: main
- Entrypoint: app.py
- Runtime: Python 3.14
- Initial application commit: 828c38258b1edde548e0a3d5b8b513f68af771ec
- Application secrets: none
- Data: bundled minimized DataCo fields and fixed predictions; no Google Drive mount
- Original local project: preserved separately

## Verified deployed behavior

Default cost, fill rate and ending inventory value match the release reference: $17,734.61, 99.02%, $145,873.51. Service objective selects the four-week baseline with 99.05% fill. Balanced exposes both the baseline and Poisson, with inspected-candidate KPIs. Unapplied changes leave results unchanged. Applying 35% annual holding gives the expected $28,186.04 cost, 98.81% fill and $133,585.52 ending inventory value.

The final evaluated week's zero replenishment reflects the inherited horizon rule; it does not represent today's inventory.

Hosted sorting and CSV download were verified. The April 10, 2017 Poisson plan totals 3,136.25 units and $187,583.09 purchase cost. Cloud settings confirm public/searchable visibility. In a separate browser, the normal Cloud wrapper intermittently remained on its loader; the direct app view loaded and worked. Use the direct link above if that occurs. This is a remaining hosting/browser loading caveat, not a substitute for a successful simulation.

## Teammate maintenance

1. Share both URLs and this project package.
2. Obtain the teammate's GitHub username. In the repository, open Settings → Collaborators and add the intended collaborator; the owner must confirm the invitation.
3. Ask the teammate to accept the invitation and clone the repository.
4. Have them run the README verification commands before changing source or data.
5. Verify their Community Cloud maintenance access and access to logs. The current deployment remains in hiokeigu's workspace; ownership transfer is not automatic.
6. Push tested changes to main to update the hosted app. Keep data and configuration in the repository. No manual Colab rerun is needed.

Cloud service availability and sleep behavior are controlled by Streamlit; this is not a guaranteed-uptime production deployment. Data redistribution terms remain unverified. Customer/contact columns are excluded from the bundled projection; no dataset license is granted here.

