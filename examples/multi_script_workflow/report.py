"""Standalone report script used by the multi-script Looma example."""

import argparse
import json
from pathlib import Path


def bump_counter(path: Path) -> None:
    count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(count + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["summary", "detailed"], required=True)
    args = parser.parse_args()

    metrics = json.loads(Path(args.input).read_text(encoding="utf-8"))

    report = {
        "mode": args.mode,
        "summary": {
            "count": metrics["count"],
            "average_score": metrics["average_score"],
        },
    }
    if args.mode == "detailed":
        report["details"] = metrics

    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    bump_counter(output.with_suffix(output.suffix + ".count"))
    print(output)


if __name__ == "__main__":
    main()
