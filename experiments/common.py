from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def looma_env(state_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not existing else str(SRC) + os.pathsep + existing
    env["LOOMA_STATE_DIR"] = str(state_dir)
    return env


def run_python(
    args: Iterable[str | Path],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *[str(arg) for arg in args]],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def latest_run(state_dir: Path) -> Path:
    runs_root = state_dir / "runs"
    runs = sorted(runs_root.iterdir(), key=lambda path: path.stat().st_mtime_ns)
    if not runs:
        raise RuntimeError(f"no Looma runs found in {runs_root}")
    return runs[-1]


def only_request(run_dir: Path) -> Path:
    requests = sorted((run_dir / "events").glob("*-script2agent.json"))
    if len(requests) != 1:
        raise RuntimeError(f"expected exactly one request, got {len(requests)} in {run_dir}")
    return requests[0]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
