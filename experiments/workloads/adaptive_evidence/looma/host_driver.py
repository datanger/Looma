"""Deterministic Host simulator for controlled W1; excluded from AEP app LOC."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from experiments.workloads.adaptive_evidence.shared.backend import FixtureSemanticBackend


ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = Path(__file__).with_name("workflow.py")


def latest_run(state_dir: Path) -> Path:
    return sorted((state_dir / "runs").iterdir(), key=lambda p: p.stat().st_mtime_ns)[-1]


def pending_request(run_dir: Path) -> Path:
    requests = sorted((run_dir / "events").glob("*-script2agent.json"))
    for request_path in reversed(requests):
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not Path(request["output"]["result_file"]).exists():
            return request_path
    raise RuntimeError("no pending script2agent request")


def run(scenario_id: str, output: str, max_rounds: int) -> int:
    backend = FixtureSemanticBackend(scenario_id)
    with tempfile.TemporaryDirectory(prefix=f"w1-looma-{scenario_id}-") as raw:
        state_dir = Path(raw) / "state"
        env = os.environ.copy()
        env["LOOMA_STATE_DIR"] = str(state_dir)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "src")
        command = [
            sys.executable, str(WORKFLOW), "--scenario", scenario_id,
            "--output", output, "--max-rounds", str(max_rounds),
        ]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)

        while result.returncode == 75:
            run_dir = latest_run(state_dir)
            request_file = pending_request(run_dir)
            request = json.loads(request_file.read_text(encoding="utf-8"))
            business_result = backend.execute(request["output"]["agent_input"])
            result_file = Path(request["output"]["result_file"])
            result_file.write_text(json.dumps(business_result, ensure_ascii=False, indent=2), encoding="utf-8")
            response_file = Path(raw) / "agent2script.json"
            response_file.write_text(json.dumps(request["expected_output"], ensure_ascii=False, indent=2), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "looma.cli", "handoff", "--request", str(request_file), "--response", str(response_file)],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )

        print(f"W1_RESULT returncode={result.returncode} elapsed_ms={(time.perf_counter() - started) * 1000:.3f}")
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.stdout.write(result.stdout)
        return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    return run(args.scenario, args.output, args.max_rounds)


if __name__ == "__main__":
    raise SystemExit(main())
