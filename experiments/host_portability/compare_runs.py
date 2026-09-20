from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    runs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in args.manifests
    ]
    hashes = {run["workflow_sha256"] for run in runs}
    same_workflow = len(hashes) == 1
    summary = {
        "schema": "aep-host-portability-comparison-v1",
        "same_workflow": same_workflow,
        "workflow_sha256": next(iter(hashes)) if same_workflow else None,
        "run_count": len(runs),
        "runs": [
            {
                "host": run["host"],
                "host_version": run["host_version"],
                "model": run["model"],
                "git_commit": run.get("git_commit"),
                "results_sha256": run["results_sha256"],
                "metrics": run.get("metrics"),
            }
            for run in runs
        ],
    }

    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)

    if not same_workflow:
        raise SystemExit(
            "Host portability comparison rejected: workflow hashes differ"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
