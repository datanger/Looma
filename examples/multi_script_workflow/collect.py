"""Standalone data collection script used by the multi-script Looma example."""

import argparse
import json
from pathlib import Path


def bump_counter(path: Path) -> None:
    count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(count + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "items": [
            {"id": "a", "score": 0.91},
            {"id": "b", "score": 0.63},
            {"id": "c", "score": 0.82},
        ]
    }
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    bump_counter(output.with_suffix(output.suffix + ".count"))
    print(output)


if __name__ == "__main__":
    main()
