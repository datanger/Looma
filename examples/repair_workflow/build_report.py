"""Build the final deterministic report for the repair workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def bump_counter(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(count + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--status", choices=["passed", "failed"], required=True)
    parser.add_argument("--repair-rounds", type=int, required=True)
    parser.add_argument("--check-json", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve()
    check = json.loads(args.check_json)
    bump_counter(repo.parent / ".counts" / "report.txt")

    report = {
        "status": args.status,
        "repair_rounds": args.repair_rounds,
        "repo": str(repo),
        "python_files": sorted(path.name for path in repo.glob("*.py")),
        "final_check": check,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
