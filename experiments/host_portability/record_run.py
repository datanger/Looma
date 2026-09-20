from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def load_json(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create an immutable-style manifest for one AEP Host portability run."
        )
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--host-version", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    workflow = args.workflow.resolve()
    results = args.results.resolve()
    if not workflow.exists() or not results.exists():
        parser.error("--workflow and --results must exist")

    root = Path(__file__).resolve().parents[2]
    manifest = {
        "schema": "aep-host-portability-run-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "host_version": args.host_version,
        "model": args.model,
        "workflow": str(workflow),
        "workflow_sha256": sha256_file(workflow),
        "results": str(results),
        "results_sha256": sha256_file(results),
        "metrics": load_json(args.metrics),
        "git_commit": git_commit(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "notes": args.notes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
