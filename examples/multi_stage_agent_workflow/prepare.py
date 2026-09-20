"""Stage A: prepare deterministic input data."""

import argparse
import json
from pathlib import Path


def bump(path: Path) -> None:
    n = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(n + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "samples": [
            {"id": "s1", "value": 8},
            {"id": "s2", "value": 13},
            {"id": "s3", "value": 21},
        ]
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bump(output.with_suffix(output.suffix + ".count"))


if __name__ == "__main__":
    main()
