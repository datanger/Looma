import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
WORKFLOW = PROJECT_ROOT / "examples" / "repair_workflow" / "workflow.py"


def _run(command, *, cwd: Path, env: dict[str, str]):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def _latest_request(run_dir: Path) -> Path:
    requests = sorted((run_dir / "events").glob("*-script2agent.json"))
    assert requests
    return requests[-1]


def _complete_agent_boundary(
    *,
    request_file: Path,
    response_file: Path,
    result: dict,
    cwd: Path,
    env: dict[str, str],
):
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        json.dumps(result),
        encoding="utf-8",
    )
    response_file.write_text(
        json.dumps(request["expected_output"]),
        encoding="utf-8",
    )
    completed = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(request_file),
            "--response",
            str(response_file),
        ],
        cwd=cwd,
        env=env,
    )
    return completed, request


def test_integrated_repair_example_loops_across_scripts_and_agent_boundaries(tmp_path: Path):
    workdir = tmp_path / "work"
    state_dir = tmp_path / "state"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)

    command = [
        sys.executable,
        str(WORKFLOW),
        "--workdir",
        str(workdir),
        "--max-repairs",
        "3",
    ]

    # prepare_workspace.py -> run_checks.py -> Agent #1
    first = _run(command, cwd=tmp_path, env=env)
    assert first.returncode == 75, first.stderr

    project = workdir / "project"
    calculator = project / "calculator.py"
    assert calculator.exists()
    assert (workdir / ".counts" / "prepare.txt").read_text() == "1"
    assert (workdir / ".counts" / "check-1.txt").read_text() == "1"

    run_dir = next((state_dir / "runs").iterdir())
    request1_file = _latest_request(run_dir)
    request1 = json.loads(request1_file.read_text(encoding="utf-8"))

    # The program returns a task description; concurrency belongs to the host.
    assert "native subagent" in request1["task"]
    assert "并发执行" in request1["task"]
    assert "不得通过 CLI、SDK、API 或 subprocess 启动另一个 Coding Agent" in request1["task"]

    # Simulate the host completing only one of two repairs so the Python loop
    # must reach a second Agent boundary.
    calculator.write_text(
        '''"""Partially repaired by the simulated host."""


def divide(a: float, b: float) -> float:
    return a / b


def clamp(value: float, low: float, high: float) -> float:
    return min(low, max(value, high))
''',
        encoding="utf-8",
    )

    second, _ = _complete_agent_boundary(
        request_file=request1_file,
        response_file=tmp_path / "agent2script-1.json",
        result={
            "changed": True,
            "summary": "fixed divide; clamp still needs repair",
            "analysis_tracks": [
                "root-cause analysis",
                "test-contract review",
                "regression-risk review",
            ],
        },
        cwd=tmp_path,
        env=env,
    )

    # replay -> run_checks.py attempt 2 -> Agent #2
    assert second.returncode == 75, second.stderr
    assert (workdir / ".counts" / "prepare.txt").read_text() == "1"
    assert (workdir / ".counts" / "check-1.txt").read_text() == "1"
    assert (workdir / ".counts" / "check-2.txt").read_text() == "1"

    request2_file = _latest_request(run_dir)
    assert request2_file != request1_file

    calculator.write_text(
        '''"""Fully repaired by the simulated host."""


def divide(a: float, b: float) -> float:
    return a / b


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))
''',
        encoding="utf-8",
    )

    third, request2 = _complete_agent_boundary(
        request_file=request2_file,
        response_file=tmp_path / "agent2script-2.json",
        result={
            "changed": True,
            "summary": "fixed clamp bounds logic",
            "analysis_tracks": [
                "root-cause analysis",
                "test-contract review",
                "regression-risk review",
            ],
        },
        cwd=tmp_path,
        env=env,
    )

    assert "native subagent" in request2["task"]

    # replay -> run_checks.py attempt 3 -> build_report.py -> complete
    assert third.returncode == 0, third.stderr

    report = json.loads((workdir / "repair-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["repair_rounds"] == 2
    assert report["final_check"]["attempt"] == 3
    assert report["final_check"]["passed"] is True

    # Each external script execution is durable: completed steps are not rerun
    # during either replay.
    counts = workdir / ".counts"
    assert (counts / "prepare.txt").read_text() == "1"
    assert (counts / "check-1.txt").read_text() == "1"
    assert (counts / "check-2.txt").read_text() == "1"
    assert (counts / "check-3.txt").read_text() == "1"
    assert (counts / "report.txt").read_text() == "1"

    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert [event["kind"] for event in state["events"]] == [
        "step",
        "step",
        "agent",
        "step",
        "agent",
        "step",
        "step",
    ]
    assert all(event["status"] == "completed" for event in state["events"])
