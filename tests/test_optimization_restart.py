import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _env(state_dir: Path, counter_file: Path, run_key: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    env["COUNTER_FILE"] = str(counter_file)
    if run_key is not None:
        env["LOOMA_RUN_KEY"] = run_key
    return env


def _write_workflow(path: Path) -> None:
    path.write_text(
        """
import json
import os
from pathlib import Path

from looma import step, workflow
from looma.optimization import CandidateProposal
from looma.optimization.engine import request_reflection
from looma.optimization.state import OptimizationState, accept_proposal


def evaluate(candidate):
    counter = Path(os.environ["COUNTER_FILE"])
    current = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
    counter.write_text(str(current + 1), encoding="utf-8")
    return {
        "outputs": [candidate["prompt"]],
        "scores": [0.5],
        "trajectories": [{"failure": "needs improvement"}],
        "side_information": [{"failure": "needs improvement"}],
        "metric_calls": 1,
    }


@workflow
def main():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    evaluation = step(evaluate, state.seed_candidate)
    proposal = request_reflection(
        task="Improve the candidate while preserving its component scope.",
        candidate=state.seed_candidate,
        evaluation=evaluation,
        frontier_ids=state.frontier.ids,
        metric_calls=evaluation["metric_calls"],
        remaining_budget=9,
    )
    accepted = step(
        accept_proposal,
        state,
        proposal,
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
        metric_calls=evaluation["metric_calls"],
    )
    if not accepted["accepted"]:
        raise RuntimeError(accepted["reason"])
    print(json.dumps(accepted["state"], ensure_ascii=False, sort_keys=True))


main()
""",
        encoding="utf-8",
    )


def _run(script: Path, cwd: Path, state_dir: Path, counter_file: Path, run_key: str | None = None):
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=_env(state_dir, counter_file, run_key),
        text=True,
        capture_output=True,
    )


def _request(state_dir: Path) -> tuple[Path, dict, Path]:
    run_dir = next((state_dir / "runs").iterdir())
    request_file = next((run_dir / "events").glob("*-script2agent.json"))
    request = json.loads(request_file.read_text(encoding="utf-8"))
    return run_dir, request, request_file


def _proposal_result(prompt: str = "improved") -> dict:
    return {
        "candidate": {"prompt": prompt},
        "components_to_update": ["prompt"],
        "rationale": "The trace identifies the missing improvement.",
        "hypothesis": "The revised prompt will improve the score.",
        "targeted_failure": "needs improvement",
    }


def _handoff(request_file: Path, request: dict, env: dict[str, str]) -> subprocess.CompletedProcess:
    response_file = request_file.parent.parent.parent / "agent2script.json"
    response_file.write_text(json.dumps(request["expected_output"]), encoding="utf-8")
    return subprocess.run(
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
        cwd=request_file.parent.parent.parent.parent,
        env=env,
        text=True,
        capture_output=True,
    )


def test_restart_replays_evaluation_and_accepts_proposal_once(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    counter_file = tmp_path / "counter.txt"
    _write_workflow(script)

    first = _run(script, tmp_path, state_dir, counter_file)
    assert first.returncode == 75
    assert counter_file.read_text(encoding="utf-8") == "1"

    run_dir, request, request_file = _request(state_dir)
    Path(request["output"]["result_file"]).write_text(
        json.dumps(_proposal_result()), encoding="utf-8"
    )
    resumed = _handoff(request_file, request, _env(state_dir, counter_file))

    assert resumed.returncode == 0, resumed.stderr
    assert counter_file.read_text(encoding="utf-8") == "1"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert len(state["events"]) == 3
    assert [event["kind"] for event in state["events"]] == ["step", "agent", "step"]
    assert state["events"][1]["status"] == "completed"
    accepted = json.loads(Path(state["events"][2]["result_file"]).read_text(encoding="utf-8"))
    assert accepted["accepted"] is True
    assert len(accepted["state"]["frontier"]["ids"]) == 1


def test_invalid_proposal_result_cannot_resume_or_mutate_state(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    counter_file = tmp_path / "counter.txt"
    _write_workflow(script)

    first = _run(script, tmp_path, state_dir, counter_file)
    assert first.returncode == 75
    run_dir, request, request_file = _request(state_dir)
    Path(request["output"]["result_file"]).write_text(
        json.dumps({"candidate": {"prompt": 3}}), encoding="utf-8"
    )
    rejected = _handoff(request_file, request, _env(state_dir, counter_file))

    assert rejected.returncode == 76
    assert counter_file.read_text(encoding="utf-8") == "1"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "waiting_agent"
    assert len(state["events"]) == 2


def test_run_keys_isolate_optimization_instances(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    counter_a = tmp_path / "counter-a.txt"
    counter_b = tmp_path / "counter-b.txt"
    _write_workflow(script)

    first_a = _run(script, tmp_path, state_dir, counter_a, "job-a")
    first_b = _run(script, tmp_path, state_dir, counter_b, "job-b")
    assert first_a.returncode == 75
    assert first_b.returncode == 75

    runs = sorted((state_dir / "runs").iterdir())
    assert len(runs) == 2
    assert {json.loads((run / "state.json").read_text())["invocation"]["run_key"] for run in runs} == {
        "job-a",
        "job-b",
    }

    for run_dir, counter_file, run_key in zip(runs, (counter_a, counter_b), ("job-a", "job-b")):
        request_file = next((run_dir / "events").glob("*-script2agent.json"))
        request = json.loads(request_file.read_text(encoding="utf-8"))
        Path(request["output"]["result_file"]).write_text(
            json.dumps(_proposal_result(run_key)), encoding="utf-8"
        )
        resumed = _handoff(
            request_file,
            request,
            _env(state_dir, counter_file, run_key),
        )
        assert resumed.returncode == 0, resumed.stderr
        assert counter_file.read_text(encoding="utf-8") == "1"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        assert state["status"] == "completed"
        accepted = json.loads(
            Path(state["events"][2]["result_file"]).read_text(encoding="utf-8")
        )
        assert accepted["accepted"] is True
