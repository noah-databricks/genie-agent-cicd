"""Benchmark gate: run the agent's benchmarks and fail the pipeline below the release criteria.

Uses the Genie benchmark evaluation API (Beta, chat mode). Release criteria:
  * accuracy (GOOD / questions run) >= --min-accuracy
  * every critical question is GOOD (zero tolerance)
NEEDS_REVIEW counts as not passed, so the run fails until someone reviews it.

  python scripts/benchmark_gate.py --target test --min-accuracy 0.9 --critical-file benchmarks/critical.txt
  python scripts/benchmark_gate.py --target dev --only-critical --critical-file benchmarks/critical.txt
  python scripts/benchmark_gate.py --target dev --questions 40000000000000000000000000000014
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent
DONE_STATES = {"DONE", "EVALUATION_CANCELLED", "EVALUATION_FAILED", "EVALUATION_TIMEOUT"}


def space_id_for(target: str, profile: str | None) -> str:
    cmd = ["databricks", "bundle", "summary", "-t", target, "-o", "json"] + (["-p", profile] if profile else [])
    summary = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    spaces = summary["resources"]["genie_spaces"]
    if len(spaces) != 1:
        sys.exit(f"expected one Genie space in the bundle, found {list(spaces)}")
    return next(iter(spaces.values()))["id"]


def read_critical(path: str | None) -> set[str]:
    if not path:
        return set()
    lines = Path(path).read_text().splitlines()
    return {l.split("#")[0].strip() for l in lines if l.split("#")[0].strip()}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--profile")
    p.add_argument("--min-accuracy", type=float, default=0.9)
    p.add_argument("--critical-file", help="benchmark question IDs that must all pass")
    p.add_argument("--only-critical", action="store_true", help="run only the critical subset (faster, cheaper)")
    p.add_argument("--questions", nargs="+", metavar="ID", help="run only these benchmark question IDs")
    p.add_argument("--timeout-min", type=int, default=30)
    args = p.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    space_id = space_id_for(args.target, args.profile)
    critical = read_critical(args.critical_file)
    subset = args.questions or (sorted(critical) if args.only_critical else None)

    run = w.genie.genie_create_eval_run(space_id, benchmark_question_ids=subset)
    print(f"eval run {run.eval_run_id} on space {space_id}: {run.num_questions} questions")
    deadline = time.time() + args.timeout_min * 60
    while True:
        run = w.genie.genie_get_eval_run(space_id, run.eval_run_id)
        status = run.eval_run_status.value if run.eval_run_status else "UNKNOWN"
        print(f"  {status}: {run.num_done}/{run.num_questions} done, {run.num_correct} correct")
        if status in DONE_STATES:
            break
        if time.time() > deadline:
            print("timed out waiting for the eval run", file=sys.stderr)
            return 1
        time.sleep(20)
    if status != "DONE":
        print(f"eval run ended with {status}", file=sys.stderr)
        return 1

    results, token = [], None
    while True:
        page = w.genie.genie_list_eval_results(space_id, run.eval_run_id, page_token=token)
        results += page.eval_results or []
        token = page.next_page_token
        if not token:
            break

    rows = []
    for r in results:
        detail = w.genie.genie_get_eval_result_details(space_id, run.eval_run_id, r.result_id)
        assessment = detail.assessment.value if detail.assessment else "NONE"
        rows.append((r.benchmark_question_id, r.question, assessment))
    rows.sort()

    good = sum(1 for _, _, a in rows if a == "GOOD")
    accuracy = good / len(rows) if rows else 0.0
    failed_critical = [(qid, q, a) for qid, q, a in rows if qid in critical and a != "GOOD"]
    passed = accuracy >= args.min_accuracy and not failed_critical

    lines = [f"### Benchmark gate: {'PASS' if passed else 'FAIL'}",
             f"Accuracy {good}/{len(rows)} = {accuracy:.0%} (threshold {args.min_accuracy:.0%}); "
             f"critical failures: {len(failed_critical)}", "",
             "| | Question | Assessment |", "|---|---|---|"]
    for qid, q, a in rows:
        mark = "critical" if qid in critical else ""
        lines.append(f"| {mark} | {q} | {a} |")
    report = "\n".join(lines)
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(report + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
