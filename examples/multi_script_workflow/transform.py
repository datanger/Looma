"""Standalone transformation script used by the multi-script Looma example."""

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
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    data = json.loads(source.read_text(encoding="utf-8"))

    scores = [float(item["score"]) for item in data["items"]]
    transformed = {
        "count": len(scores),
        "average_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
    }

    output.write_text(
        json.dumps(transformed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    bump_counter(output.with_suffix(output.suffix + ".count"))
    print(output)


if __name__ == "__main__":
    main()
