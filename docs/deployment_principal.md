# Deployment principals

Two facts from the docs drive this design:

- Prompt-matching values (value dictionary, entity matching) "are generated using the author's data permissions. These values become part of the agent's shared context" ([tune quality](https://docs.databricks.com/gcp/en/genie-agents/tune-quality)). A bundle-deployed agent's author is the principal that deployed it.
- Views and metric views resolve their sources with the owner's privileges: "The metric view owner's privileges are used to resolve the underlying data sources at query time" ([metric views](https://docs.databricks.com/gcp/en/metric-views/create/sql)). Agent users only need `SELECT` on the agent schema, never on gold.

A broad platform principal (for example the Terraform service account) that deploys agents can therefore expose sample values from any table it can read. Separate the identities instead.

## Recommended split

| Principal | Does | Unity Catalog | Workspace |
|---|---|---|---|
| **dbt build** (existing dbt runner) | Builds gold and the agent schema; owns the metric views | `USE CATALOG`; on gold: `USE SCHEMA`, `CREATE TABLE`, `MODIFY`, `SELECT`; on the agent schema: `USE SCHEMA`, `CREATE TABLE`, `MANAGE` (to grant the users group) | `CAN USE` on the warehouse |
| **Genie deployer** (one per domain, e.g. `sp-genie-portfolio-reporting`) | Runs `bundle deploy` for the agent; becomes the agent's author | `USE CATALOG`; on the agent schema only: `USE SCHEMA`, `SELECT` | Databricks SQL entitlement; `CAN USE` on the warehouse; owns its bundle root folder |
| **Agent users** (IdP-synced account group) | Ask questions | On the agent schema: `USE SCHEMA`, `SELECT` (granted by the dbt on-run-end hook) | `CAN RUN` on the agent (set by the bundle) |

Result: the deployer can only see the curated agent schema, so prompt-matching values can only come from data that the agent's users are already entitled to see. Turn off prompt matching on sensitive columns anyway (`enable_entity_matching: false` in the agent file's `column_configs`).

Requirements to create an agent ([set up](https://docs.databricks.com/gcp/en/genie-agents/set-up)): Databricks SQL entitlement, `CAN USE` on a pro or serverless warehouse, `SELECT` on the agent's data. Creators get `CAN MANAGE` on the agent.

## Grants (run once per environment by the platform team)

```sql
-- Agent schema created by the platform, not by dbt
CREATE SCHEMA IF NOT EXISTS prd_genie.portfolio_reporting;

-- dbt build principal
GRANT USE CATALOG ON CATALOG prd_genie TO `sp-dbt-build`;
GRANT USE SCHEMA, CREATE TABLE, MANAGE ON SCHEMA prd_genie.portfolio_reporting TO `sp-dbt-build`;

-- Genie deployer: the agent schema and nothing else
GRANT USE CATALOG ON CATALOG prd_genie TO `sp-genie-portfolio-reporting`;
GRANT USE SCHEMA, SELECT ON SCHEMA prd_genie.portfolio_reporting TO `sp-genie-portfolio-reporting`;
```

Workspace side: give the deployer the Databricks SQL entitlement and `CAN USE` on the agent warehouse. In `databricks.yml`, uncomment `run_as` on the prod target and run CI as that principal.

## In this repo

The demo uses one identity for dbt and deploy. To split them in CI, give the `run_dbt.py` step the dbt principal's credentials and the `bundle deploy` / gate steps the Genie deployer's.
