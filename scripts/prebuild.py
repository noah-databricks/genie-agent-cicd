"""Render the Genie agent file for one bundle target.

Bundle variables don't reach inside the serialised agent file, so the source file
(src/genie/*.geniespace.json) uses ${catalog}, ${gold_schema} and ${genie_schema}
placeholders and this script writes the resolved copy to build/ before deploy.

Values come from `databricks bundle validate -t <target> -o json`, so anything the
bundle can resolve (per-user dev schemas, target overrides) is honoured, and the
agent file can never point at a different environment from the rest of the bundle.

  python scripts/prebuild.py --target dev
  python scripts/prebuild.py --verify prod      # CI guard: build/ was rendered for prod
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "genie"
BUILD = ROOT / "build"
MARKER = BUILD / ".build_target"
PLACEHOLDER = re.compile(r"\$\{(catalog|gold_schema|genie_schema)\}")


def resolve_variables(target: str, profile: str | None) -> dict:
    # validate reads build/ files, so make sure each one exists before resolving.
    BUILD.mkdir(exist_ok=True)
    for src in SRC.glob("*.geniespace.json"):
        out = BUILD / src.name
        if not out.exists():
            out.write_text(src.read_text())

    cmd = ["databricks", "bundle", "validate", "-t", target, "-o", "json"]
    if profile:
        cmd += ["-p", profile]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"bundle validate failed for target '{target}':\n{res.stderr}")
    variables = json.loads(res.stdout)["variables"]
    return {k: v.get("value") for k, v in variables.items()}


def render(target: str, profile: str | None) -> None:
    values = resolve_variables(target, profile)
    for src in SRC.glob("*.geniespace.json"):
        text = src.read_text()
        missing = {m for m in PLACEHOLDER.findall(text) if not values.get(m)}
        if missing:
            sys.exit(f"{src.name}: no value for {sorted(missing)} in target '{target}'")
        rendered = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
        json.loads(rendered)  # fail fast on a broken agent file
        (BUILD / src.name).write_text(rendered)
        print(f"rendered {src.name} -> build/ ({values['catalog']}.{values['genie_schema']})")
    MARKER.write_text(target + "\n")


def verify(target: str) -> int:
    if not MARKER.exists():
        print(f"build/ not rendered. Run: python scripts/prebuild.py --target {target}", file=sys.stderr)
        return 1
    actual = MARKER.read_text().strip()
    if actual != target:
        print(f"build/ was rendered for '{actual}', expected '{target}'", file=sys.stderr)
        return 1
    leftover = [p.name for p in BUILD.glob("*.geniespace.json") if PLACEHOLDER.search(p.read_text())]
    if leftover:
        print(f"unresolved placeholders in {leftover}", file=sys.stderr)
        return 1
    print(f"build/ matches target '{target}'")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target")
    group.add_argument("--verify", metavar="TARGET")
    parser.add_argument("--profile", help="Databricks CLI profile (optional; CI uses env auth)")
    args = parser.parse_args()
    if args.verify:
        sys.exit(verify(args.verify))
    render(args.target, args.profile)
