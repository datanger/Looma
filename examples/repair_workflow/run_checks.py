"""Run deterministic tests for the project being repaired."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(repo),
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    print(
        json.dumps(
            {
                "attempt": args.attempt,
                "passed": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-12000:],
                "stderr": completed.stderr[-12000:],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
