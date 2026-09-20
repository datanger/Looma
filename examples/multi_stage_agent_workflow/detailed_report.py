"""Stage E: produce a detailed report."""

import argparse
import json
from pathlib import Path


def bump(path: Path) -> None:
    n = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(n + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    gate = json.loads(Path(args.gate).read_text(encoding="utf-8"))

    result = {
        "kind": "detailed",
        "analysis": analysis,
        "gate": gate,
    }

    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    bump(output.with_suffix(output.suffix + ".count"))


if __name__ == "__main__":
    main()
