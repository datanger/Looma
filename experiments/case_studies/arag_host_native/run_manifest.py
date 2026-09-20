from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


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


def file_record(path: Path | None):
    if path is None:
        return None
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "sha256": digest(resolved),
        "bytes": resolved.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["original-arag", "aep-host-native"], required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--subset-manifest", type=Path)
    parser.add_argument("--index-file", type=Path)
    parser.add_argument("--host", default="")
    parser.add_argument("--host-version", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--arag-commit", required=True)
    parser.add_argument("--looma-commit", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    payload = {
        "schema": "aep-arag-run-manifest-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "dataset": args.dataset,
        "host": args.host,
        "host_version": args.host_version,
        "model": args.model,
        "arag_commit": args.arag_commit,
        "looma_commit": args.looma_commit or git_commit(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "questions": file_record(args.questions),
        "chunks": file_record(args.chunks),
        "config": file_record(args.config),
        "predictions": file_record(args.predictions),
        "subset_manifest": file_record(args.subset_manifest),
        "index_file": file_record(args.index_file),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
