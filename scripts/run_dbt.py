"""Run dbt against a bundle target's catalog, schemas and warehouse.

Bundle targets stay the single source of truth for environment names: this script
reads them with `databricks bundle validate` and passes them to dbt, so dbt can't
build into a different environment from the one the agent deploys to.

  python scripts/run_dbt.py --target test            # dbt build
  python scripts/run_dbt.py --target dev -- run -s genie   # any dbt args after --
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

parser = argparse.ArgumentParser()
parser.add_argument("--target", required=True)
parser.add_argument("--profile", help="Databricks CLI profile for local runs; CI uses OAuth M2M env vars")
parser.add_argument("dbt_args", nargs="*", default=["build"])
args = parser.parse_args()

cli = ["-p", args.profile] if args.profile else []
# validate reads the rendered agent file, which doesn't exist yet on a fresh checkout
(ROOT / "build").mkdir(exist_ok=True)
for src in (ROOT / "src" / "genie").glob("*.geniespace.json"):
    if not (ROOT / "build" / src.name).exists():
        (ROOT / "build" / src.name).write_text(src.read_text())
res = subprocess.run(["databricks", "bundle", "validate", "-t", args.target, "-o", "json", *cli],
                     cwd=ROOT, capture_output=True, text=True)
if res.returncode != 0:
    sys.exit(f"bundle validate failed for target '{args.target}':\n{res.stderr}")
bundle = json.loads(res.stdout)
v = {k: x.get("value") for k, x in bundle["variables"].items()}

env = dict(os.environ,
           DATABRICKS_HOST=bundle["workspace"]["host"],
           DBT_WAREHOUSE_ID=v["warehouse_id"],
           DBT_CATALOG=v["catalog"],
           DBT_GOLD_SCHEMA=v["gold_schema"])
if "DATABRICKS_CLIENT_ID" in env:
    env["DBT_AUTH"] = "oauth_m2m"
elif "DATABRICKS_TOKEN" not in env:
    token = subprocess.run(["databricks", "auth", "token", *cli], capture_output=True, text=True, check=True)
    env["DATABRICKS_TOKEN"] = json.loads(token.stdout)["access_token"]

dbt_vars = json.dumps({"gold_schema": v["gold_schema"], "genie_schema": v["genie_schema"],
                       "agent_users_group": v["agent_users_group"]})
cmd = [os.environ.get("DBT", "dbt"), *args.dbt_args, "--profiles-dir", "ci_profiles", "--vars", dbt_vars]
print(f"[{args.target}] {v['catalog']}.{v['gold_schema']} / {v['genie_schema']}")
sys.exit(subprocess.run(cmd, cwd=ROOT / "dbt", env=env).returncode)
