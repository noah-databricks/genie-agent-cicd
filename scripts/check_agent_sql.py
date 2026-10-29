"""Run every example SQL and benchmark answer in the rendered agent file.

A cheap CI check (SQL warehouse only, no Genie usage) that catches broken
references before the benchmark gate: renamed columns, dropped measures, a
metric view missing from the target schema.

  python scripts/check_agent_sql.py --target test
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

ROOT = Path(__file__).resolve().parent.parent


def bundle_value(target: str, profile: str | None, key: str) -> str:
    cmd = ["databricks", "bundle", "validate", "-t", target, "-o", "json"] + (["-p", profile] if profile else [])
    out = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    return out["variables"][key]["value"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    warehouse_id = bundle_value(args.target, args.profile, "warehouse_id")

    failures = 0
    for path in sorted((ROOT / "build").glob("*.geniespace.json")):
        agent = json.loads(path.read_text())
        checks = [("example", e["question"][0], "".join(e["sql"]))
                  for e in agent.get("instructions", {}).get("example_question_sqls", [])]
        checks += [("benchmark", b["question"][0], "".join(b["answer"][0]["content"]))
                   for b in agent.get("benchmarks", {}).get("questions", [])]
        for kind, question, sql in checks:
            res = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id, statement=sql, wait_timeout="50s", row_limit=5)
            state = res.status.state
            rows = res.result.row_count if res.result and res.result.row_count is not None else 0
            if state != StatementState.SUCCEEDED or rows == 0:
                failures += 1
                err = res.status.error.message if res.status.error else f"{rows} rows"
                print(f"FAIL [{kind}] {question}\n     {err}")
            else:
                print(f"ok   [{kind}] {question} ({rows} rows)")
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
