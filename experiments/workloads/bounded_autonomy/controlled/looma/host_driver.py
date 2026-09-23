"""Deterministic Host simulator for the controlled RQ2 comparison.

This file is not application code. It stands in for the already-running Host Agent that a
real AEP deployment would reuse: it consumes `script2agent`, performs the semantic work
with the same deterministic driver policy every other paradigm gets, writes the business
result into `output.result_file`, and resumes the original command through the guarded
handoff. Its own trace is written to a sidecar file so the Host-owned tool route can be
reported next to the application-owned route.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.workloads.bounded_autonomy.controlled.policy import AdaptiveDriverPolicy
from experiments.workloads.bounded_autonomy.controlled.protocol import (
    HOST_NATIVE_ACTIONS,
    RouteMissing,
    ToolSession,
)


# host_driver.py -> looma/ -> controlled/ -> bounded_autonomy/ -> workloads/ -> experiments/ -> repo
ROOT = Path(__file__).resolve().parents[5]
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


def perform_boundary(request: dict) -> tuple[dict, dict]:
    """Host-native execution of one semantic boundary."""
    boundary_input = request["output"]["agent_input"]
    policy = AdaptiveDriverPolicy(boundary_input["scenario"])
    policy.note_feedback(boundary_input.get("previous_validation_problems"))
    session = ToolSession(boundary_input["scenario_id"], HOST_NATIVE_ACTIONS)
    while True:
        action = policy.next_request(session)
        if action["kind"] == "finish":
            break
        try:
            session.execute(action)
        except RouteMissing:  # cannot happen for a Host-owned route set
            raise
    return action["result"], {
        "declared_actions": list(HOST_NATIVE_ACTIONS),
        "tool_path": list(session.tool_path),
        "actions_used": len(session.observations),
        "round": boundary_input.get("round"),
    }


def run(scenario_id: str, output: str, max_rounds: int) -> int:
    with tempfile.TemporaryDirectory(prefix=f"rq2-looma-{scenario_id}-") as raw:
        raw_root = Path(raw)
        state_dir = raw_root / "state"
        env = os.environ.copy()
        env["LOOMA_STATE_DIR"] = str(state_dir)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "src")
        command = [
            sys.executable, str(WORKFLOW), "--scenario", scenario_id,
            "--output", output, "--max-rounds", str(max_rounds),
        ]
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)

        boundaries: list[dict] = []
        while result.returncode == 75:
            run_dir = latest_run(state_dir)
            request_file = pending_request(run_dir)
            request = json.loads(request_file.read_text(encoding="utf-8"))
            business_result, trace = perform_boundary(request)
            boundaries.append(trace)
            Path(request["output"]["result_file"]).write_text(
                json.dumps(business_result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            response_file = raw_root / "agent2script.json"
            response_file.write_text(
                json.dumps(request["expected_output"], ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable, "-m", "looma.cli", "handoff",
                    "--request", str(request_file), "--response", str(response_file),
                ],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )

        host_trace = {
            "implementation": "looma_host",
            "routes_mode": "host_native",
            "declared_actions": list(HOST_NATIVE_ACTIONS),
            "route_gaps": [],
            "rounds": len(boundaries),
            "actions_used": sum(item["actions_used"] for item in boundaries),
            "tool_path": [action for item in boundaries for action in item["tool_path"]],
            "boundaries": boundaries,
        }
        Path(f"{output}.host.json").write_text(
            json.dumps(host_trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.stdout.write(result.stdout)
        else:
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