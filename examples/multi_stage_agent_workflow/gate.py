"""Stage C: deterministically validate Agent #2's requested report route."""

import argparse
import json
from pathlib import Path


def bump(path: Path) -> None:
    n = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(n + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--route", choices=["summary", "detailed"], required=True)
    parser.add_argument("--approved", choices=["true", "false"], required=True)
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    approved = args.approved == "true"

    # Programmatic rule: rejected analysis must always be routed to detailed output.
    route = args.route if approved else "detailed"
    gate = {
        "approved": approved,
        "route": route,
        "analysis_average": analysis["average"],
        "analysis_maximum": analysis["maximum"],
    }

    output = Path(args.output)
    output.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    bump(output.with_suffix(output.suffix + ".count"))


if __name__ == "__main__":
    main()
