import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
WORKFLOW = PROJECT_ROOT / "examples" / "multi_stage_agent_workflow" / "workflow.py"


def _run(command, *, cwd, env):
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


def test_multi_stage_workflow_two_agent_boundaries_and_final_branch(tmp_path: Path):
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
    ]

    # First process: Stage A -> Agent #1 -> suspend.
    first = _run(command, cwd=tmp_path, env=env)
    assert first.returncode == 75, first.stderr
    assert (workdir / "prepared.json").exists()
    assert not (workdir / "analysis.json").exists()
    assert (workdir / "prepared.json.count").read_text(encoding="utf-8") == "1"

    runs = list((state_dir / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]

    req1_file = _latest_request(run_dir)
    req1 = json.loads(req1_file.read_text(encoding="utf-8"))
    Path(req1["output"]["result_file"]).write_text(
        '{"strategy":"aggressive","reason":"exercise stage B"}',
        encoding="utf-8",
    )
    response1 = tmp_path / "agent2script-1.json"
    response1.write_text(json.dumps(req1["expected_output"]), encoding="utf-8")

    # Second process: replay A -> Agent #1 result -> Stage B -> Agent #2 -> suspend.
    second = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(req1_file),
            "--response",
            str(response1),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert second.returncode == 75, second.stderr
    assert (workdir / "analysis.json").exists()
    assert not (workdir / "gate.json").exists()
    assert (workdir / "prepared.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "analysis.json.count").read_text(encoding="utf-8") == "1"

    req2_file = _latest_request(run_dir)
    assert req2_file != req1_file
    req2 = json.loads(req2_file.read_text(encoding="utf-8"))
    Path(req2["output"]["result_file"]).write_text(
        '{"approved":true,"route":"summary","reason":"analysis is accepted"}',
        encoding="utf-8",
    )
    response2 = tmp_path / "agent2script-2.json"
    response2.write_text(json.dumps(req2["expected_output"]), encoding="utf-8")

    # Third process: replay A/B and both Agent results -> Stage C -> summary branch.
    third = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(req2_file),
            "--response",
            str(response2),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert third.returncode == 0, third.stderr

    final = json.loads((workdir / "final.json").read_text(encoding="utf-8"))
    assert final["kind"] == "summary"
    assert final["strategy"] == "aggressive"
    assert final["approved"] is True

    # Every external script must execute exactly once despite two resumes.
    assert (workdir / "prepared.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "analysis.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "gate.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "final.json.count").read_text(encoding="utf-8") == "1"


def test_multi_stage_workflow_rejected_review_forces_detailed_branch(tmp_path: Path):
    workdir = tmp_path / "work"
    state_dir = tmp_path / "state"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)

    command = [sys.executable, str(WORKFLOW), "--workdir", str(workdir)]
    first = _run(command, cwd=tmp_path, env=env)
    assert first.returncode == 75

    run_dir = next((state_dir / "runs").iterdir())
    req1_file = _latest_request(run_dir)
    req1 = json.loads(req1_file.read_text(encoding="utf-8"))
    Path(req1["output"]["result_file"]).write_text(
        '{"strategy":"conservative","reason":"stable baseline"}',
        encoding="utf-8",
    )
    response1 = tmp_path / "response1.json"
    response1.write_text(json.dumps(req1["expected_output"]), encoding="utf-8")

    second = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(req1_file),
            "--response",
            str(response1),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert second.returncode == 75

    req2_file = _latest_request(run_dir)
    req2 = json.loads(req2_file.read_text(encoding="utf-8"))
    Path(req2["output"]["result_file"]).write_text(
        '{"approved":false,"route":"summary","reason":"force deterministic gate"}',
        encoding="utf-8",
    )
    response2 = tmp_path / "response2.json"
    response2.write_text(json.dumps(req2["expected_output"]), encoding="utf-8")

    third = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(req2_file),
            "--response",
            str(response2),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert third.returncode == 0, third.stderr

    final = json.loads((workdir / "final.json").read_text(encoding="utf-8"))
    assert final["kind"] == "detailed"
    assert final["gate"]["approved"] is False
    assert final["gate"]["route"] == "detailed"
