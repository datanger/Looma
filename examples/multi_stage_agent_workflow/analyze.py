"""Stage B: analyze prepared data using the strategy chosen by Agent #1."""

import argparse
import json
from pathlib import Path


def bump(path: Path) -> None:
    n = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(n + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strategy", choices=["conservative", "aggressive"], required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    values = [int(item["value"]) for item in data["samples"]]

    multiplier = 1 if args.strategy == "conservative" else 2
    scores = [value * multiplier for value in values]

    output_data = {
        "strategy": args.strategy,
        "count": len(scores),
        "scores": scores,
        "average": sum(scores) / len(scores),
        "maximum": max(scores),
    }

    output = Path(args.output)
    output.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
    bump(output.with_suffix(output.suffix + ".count"))


if __name__ == "__main__":
    main()
