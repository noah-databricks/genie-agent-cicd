# Genie agent CI/CD reference

A Genie agent and its data objects managed as code with Declarative Automation Bundles and dbt, promoted dev → test → prod with automated gates. Built on the public reference implementation ([databricks-solutions/databricks-blogposts/2026-08-genie-agent-cicd](https://github.com/databricks-solutions/databricks-blogposts/tree/main/2026-08-genie-agent-cicd)) and extended for a dbt shop with separately named environments.

The data is synthetic (3,000 accounts, 24 month-ends). Replace `dbt/models/synthetic` and the gold models with real `ref()`/`source()` models.

Sample code, provided as is: it isn't an officially supported Databricks product. Review and adapt it before using it in your environments.

## Setup

1. **Targets.** In `databricks.yml`, set each target's `host` and `catalog` (and the schema names if you prefer others). The warehouse is looked up by name (`Serverless Starter Warehouse`); change the lookup to your agent warehouse.
2. **Users group.** Set `agent_users_group` to the account group (synced from your IdP) that should use the agent. It gets `CAN_RUN` on the agent and `SELECT` on the agent schema.
3. **Deployment service principal.** Create one per agent or domain, give it the Databricks SQL entitlement, `CAN USE` on the warehouse, and `USE CATALOG` + `CREATE SCHEMA` on the test and prod catalogs. See `docs/deployment_principal.md` for why it should be scoped this narrowly.
4. **CI secrets.** GitHub: repository variable `DATABRICKS_HOST`, secrets `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` (an OAuth secret for the principal), and environments `test` and `production` (restrict `production` to `v*` tags and add the agent owner as a required reviewer). Azure DevOps: variable group `databricks-genie-deployer` and environments `genie-test` / `genie-production`.
5. **First deploy to dev** from a laptop:
   ```bash
   pip install -r requirements-ci.txt
   python scripts/run_dbt.py --target dev --profile <profile>
   python scripts/prebuild.py --target dev --profile <profile>
   databricks bundle deploy -t dev -p <profile>
   ```
6. **First release:** push a `v1.0.0` tag to deploy test-approved code to prod.

## Layout

```
databricks.yml                      bundle, variables, dev / test / prod targets
resources/
  portfolio_reporting.genie_space.yml   agent resource: title, warehouse, folder, CAN_RUN group
  portfolio_dbt.job.yml                 scheduled dbt build (Databricks dbt task)
src/genie/portfolio_reporting.geniespace.json
                                    agent file (instructions, example SQL, benchmarks) with
                                    ${catalog} / ${genie_schema} placeholders: the source of truth
dbt/
  models/gold/                      gold tables (persist_docs writes descriptions to UC)
  models/genie/                     the agent's schema: three metric views (metric_view materialisation)
  ci_profiles/profiles.yml          profile for laptop / CI runs
benchmarks/critical.txt             benchmark IDs with zero tolerance
scripts/
  prebuild.py                       render the agent file for a target into build/
  run_dbt.py                        dbt build against a target's catalog / schemas / warehouse
  check_agent_sql.py                execute every example and benchmark SQL (no Genie cost)
  benchmark_gate.py                 run benchmarks via the API and enforce release criteria
  pull_from_workspace.py            bring UI edits from dev back into the agent file
.github/workflows/                  pr.yml (validate, test, gate), release.yml (tag → prod)
azure-pipelines.yml                 the same flow for Azure DevOps
docs/deployment_principal.md        who deploys, with which grants, and why
```

## Environments

| Target | Mode | Schemas | Who deploys |
|---|---|---|---|
| `dev` | development (resources prefixed `[dev <user>]`) | `analytics_dev.<user>_portfolio_{gold,genie}` | each developer |
| `test` | default | `analytics_tst.portfolio_{gold,genie}` | CI on every PR |
| `prod` | production | `analytics_prd.portfolio_{gold,genie}` | CI on a version tag, after owner approval |

Environment differences live only in the targets. Bundle variables don't reach inside the agent file, so `prebuild.py` renders it per target from the values `databricks bundle validate` resolves. The agent file can't point at a different environment from the rest of the bundle.

## Developer loop

```bash
python scripts/run_dbt.py --target dev --profile <profile>      # data objects first
python scripts/prebuild.py --target dev --profile <profile>
databricks bundle deploy -t dev -p <profile>
# ... tune the agent in the Genie UI ...
python scripts/pull_from_workspace.py --target dev --profile <profile>
git diff src/genie                                               # only what changed, with placeholders
python scripts/benchmark_gate.py --target dev --profile <profile> --questions <id> ...   # scoped check
```

Order matters: the agent can't be created until its tables exist, so dbt always runs before `bundle deploy`.

## Pipeline

1. **PR:** render and `bundle validate` every target, `dbt parse`, dbt build in test, deploy to test, `check_agent_sql.py`, `benchmark_gate.py` (accuracy ≥ 90%, every critical question GOOD; NEEDS_REVIEW counts as a fail).
2. **Release:** merge, tag `vX.Y.Z`, the `production` environment approval (agent owner), dbt build in prod, deploy, SQL check.
3. **Rollback:** re-run the release workflow on the previous tag. The agent is updated in place and keeps its ID, so existing links keep working.
4. **Drift:** `databricks bundle plan -t prod` reports any edit made in the prod UI; the next deploy reverts it.

## Release criteria (agree with the agent owner)

- ~20 benchmark questions across the domain, written and reviewed by people, not generated.
- Accuracy threshold (90% here; higher for external-facing agents).
- Zero tolerance on `benchmarks/critical.txt`.
- No regression versus the last release (compare with the previous run in `genie-list-eval-runs`; not automated here).

Benchmark runs use Genie compute and take ~30 seconds per question. Run a scoped subset during development and the full suite in the PR gate.
