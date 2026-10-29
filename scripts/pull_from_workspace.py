"""Pull UI edits from a deployed agent back into the source agent file.

Develop in the Genie UI in dev, then run this to bring the change into git. It
wraps `databricks bundle generate genie-space`, swaps the target's resolved
names back to ${catalog} / ${gold_schema} / ${genie_schema}, and writes lists in
a stable order so the PR diff shows only what changed.

  python scripts/pull_from_workspace.py --target dev
  git diff src/genie
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "portfolio_reporting"


def canonical(obj):
    """Stable ordering: items with an id by id, column configs by name, tables by identifier."""
    if isinstance(obj, dict):
        return {k: canonical(v) for k, v in obj.items()}
    if isinstance(obj, list):
        items = [canonical(v) for v in obj]
        for field in ("id", "column_name", "identifier"):
            if items and all(isinstance(i, dict) and field in i for i in items):
                return sorted(items, key=lambda i: i[field])
        return items
    return obj


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="dev")
    p.add_argument("--profile")
    args = p.parse_args()
    cli = ["-t", args.target] + (["-p", args.profile] if args.profile else [])

    summary = json.loads(subprocess.run(["databricks", "bundle", "summary", "-o", "json", *cli],
                                        cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    space_id = summary["resources"]["genie_spaces"][KEY]["id"]
    v = {k: x.get("value") for k, x in summary["variables"].items()}

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["databricks", "bundle", "generate", "genie-space", "--existing-id", space_id,
                        "--key", KEY, "-d", f"{tmp}/resources", "-s", f"{tmp}/src", *cli],
                       cwd=ROOT, capture_output=True, text=True, check=True)
        text = Path(tmp, "src", f"{KEY}.geniespace.json").read_text()

    # Resolved names back to placeholders, plain or backtick-quoted (Genie-authored SQL quotes them).
    for schema_var in ("genie_schema", "gold_schema"):
        cat, sch = v["catalog"], v[schema_var]
        text = re.sub(rf"`{re.escape(cat)}`\.`{re.escape(sch)}`", f"${{catalog}}.${{{schema_var}}}", text)
        text = text.replace(f"{cat}.{sch}", f"${{catalog}}.${{{schema_var}}}")
    leftover = re.findall(rf"\b{re.escape(v['catalog'])}\.\w+", text)
    if leftover:
        print(f"warning: references outside the agent's schemas: {sorted(set(leftover))}", file=sys.stderr)

    out = ROOT / "src" / "genie" / f"{KEY}.geniespace.json"
    out.write_text(json.dumps(canonical(json.loads(text)), indent=2, sort_keys=True) + "\n")
    print(f"pulled space {space_id} ({args.target}) -> {out.relative_to(ROOT)}")
    subprocess.run(["git", "diff", "--stat", "--", str(out)], cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
