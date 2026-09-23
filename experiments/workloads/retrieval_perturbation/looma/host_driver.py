"""Deterministic Host simulator for the retrieval-perturbation comparison.

This file is not application code. It stands in for the already-running Host
Agent an AEP deployment would reuse: it consumes `script2agent`, performs the
retrieval with the same deterministic driver every other paradigm gets, persists
the retrieval session, writes the business result into `output.result_file`, and
resumes the original command through the guarded handoff.

Its route set is Host-owned, so it is complete for every perturbation. That is
the whole difference from the direct-SDK baseline: widening costs the Host a
line and costs the application nothing. The Host trace is written to a sidecar
file so it can be reported next to the application-owned route.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.workloads.retrieval_perturbation.driver import AdaptiveRetrievalDriver
from experiments.workloads.retrieval_perturbation.injectors import (
    HOST_NATIVE_ROUTE_SET,
    Environment,
)
from experiments.workloads.retrieval_perturbation.protocol import (
    MAX_ACTIONS_PER_ROUND,
    ActionBudgetExceeded,
    RetrievalSession,
    RouteMissing,
    write_session,
)


# host_driver.py -> looma/ -> retrieval_perturbation/ -> workloads/ -> experiments/ -> repo
ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = Path(__file__).with_name("workflow.py")


def latest_run(state_dir: Path) -> Path:
    return sorted((state_dir / "runs").iterdir(), key=lambda p: p.stat().st_mtime_ns)[-1]


def pending_request(run_dir: Path) -> Path:
    for request_path in reversed(sorted((run_dir / "events").glob("*-script2agent.json"))):
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not Path(request["output"]["result_file"]).exists():
            return request_path
    raise RuntimeError("no pending script2agent request")


def perform_boundary(request: dict) -> tuple[dict, dict]:
    boundary_input = request["output"]["agent_input"]
    instance_file = boundary_input["instance_file"]
    session_file = boundary_input["session_file"]

    environment = Environment.from_payload(
        json.loads(Path(instance_file).read_text(encoding="utf-8"))
    )
    session = RetrievalSession(
        environment,
        HOST_NATIVE_ROUTE_SET,
        max_actions=MAX_ACTIONS_PER_ROUND,
    )
    driver = AdaptiveRetrievalDriver(environment.question)

    budget_exceeded = None
    try:
        while True:
            action = driver.next_action(session)
            if action is None:
                break
            try:
                session.execute(action)
            except RouteMissing:  # cannot happen for a Host-owned route set
                raise
    except ActionBudgetExceeded as exceeded:
        budget_exceeded = f"{exceeded.used} > {exceeded.limit}"

    result = driver.finish(session)
    write_session(session_file, session.as_dict(result["status"]))
    trace = {
        "declared_actions": list(HOST_NATIVE_ROUTE_SET),
        "environment_actions": list(environment.available_actions),
        "tool_path": list(session.tool_path),
        "actions_used": len(session.observations),
        "route_gaps": [],
        "round": boundary_input.get("round"),
        "budget_exceeded": budget_exceeded,
    }
    return result, trace


def run(instance_file: str, output: str, session_file: str, max_rounds: int) -> int:
    instance_key = Path(instance_file).stem
    with tempfile.TemporaryDirectory(prefix=f"aep-retrieval-{instance_key}-") as raw:
        raw_root = Path(raw)
        state_dir = raw_root / "state"
        env = os.environ.copy()
        env["LOOMA_STATE_DIR"] = str(state_dir)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "src")
        command = [
            sys.executable, str(WORKFLOW),
            "--instance", instance_file,
            "--output", output,
            "--session", session_file,
            "--max-rounds", str(max_rounds),
        ]
        completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)

        boundaries: list[dict] = []
        while completed.returncode == 75:
            request_file = pending_request(latest_run(state_dir))
            request = json.loads(request_file.read_text(encoding="utf-8"))
            business_result, trace = perform_boundary(request)
            boundaries.append(trace)
            Path(request["output"]["result_file"]).write_text(
                json.dumps(business_result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            response_file = raw_root / "agent2script.json"
            response_file.write_text(
                json.dumps(request["expected_output"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable, "-m", "looma.cli", "handoff",
                    "--request", str(request_file), "--response", str(response_file),
                ],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )

        host_trace = {
            "implementation": "looma_host",
            "routes_mode": "host_native",
            "declared_actions": list(HOST_NATIVE_ROUTE_SET),
            "route_gaps": [],
            "rounds": len(boundaries),
            "actions_used": sum(item["actions_used"] for item in boundaries),
            "tool_path": [action for item in boundaries for action in item["tool_path"]],
            "boundaries": boundaries,
        }
        Path(f"{output}.host.json").write_text(
            json.dumps(host_trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
        sys.stdout.write(completed.stdout)
        return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--max-rounds", type=int, default=2)
    args = parser.parse_args()
    return run(args.instance, args.output, args.session, args.max_rounds)


if __name__ == "__main__":
    raise SystemExit(main())