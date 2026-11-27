"""The stable part of the API (see app/api/contract.py), for the 1.x compatibility check.

python -m app.cli.api_contract show                 # the stable schema to stdout
python -m app.cli.api_contract check <baseline>     # list breaking changes, exit 1 if there are any
python -m app.cli.api_contract write <baseline>     # (re)write the baseline: only once, for 1.0.0
"""

import argparse
import json
import sys
from pathlib import Path

from app.api.contract import breaking_changes, stable_schema
from app.main import app


def current() -> dict:
    return stable_schema(app.openapi())


def dump(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=1) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="The stable part of the pomale API")
    parser.add_argument("action", choices=("show", "check", "write"))
    parser.add_argument("baseline", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "show":
        sys.stdout.write(dump(current()))
        return
    if args.baseline is None:
        parser.error("check and write need the baseline file")
    if args.action == "write":
        args.baseline.write_text(dump(current()), encoding="utf-8")
        return
    problems = breaking_changes(json.loads(args.baseline.read_text(encoding="utf-8")), current())
    for problem in problems:
        print(problem)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
