import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
WORKFLOW = PROJECT_ROOT / "examples" / "multi_script_workflow" / "workflow.py"


def test_multi_script_workflow_resumes_without_reexecuting_completed_scripts(tmp_path: Path):
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

    first = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert first.returncode == 75, first.stderr
    assert (workdir / "raw.json").exists()
    assert (workdir / "processed.json").exists()
    assert not (workdir / "report.json").exists()
    assert (workdir / "raw.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "processed.json.count").read_text(encoding="utf-8") == "1"

    runs = list((state_dir / "runs").iterdir())
    assert len(runs) == 1
    events_dir = runs[0] / "events"
    requests = list(events_dir.glob("*-script2agent.json"))
    assert len(requests) == 1

    request_file = requests[0]
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        '{"mode":"summary","reason":"metrics are compact"}',
        encoding="utf-8",
    )

    response_file = tmp_path / "agent2script.json"
    response_file.write_text(
        json.dumps(request["expected_output"]),
        encoding="utf-8",
    )

    resumed = subprocess.run(
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
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert resumed.returncode == 0, resumed.stderr
    assert (workdir / "report.json").exists()

    report = json.loads((workdir / "report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "summary"
    assert report["summary"]["count"] == 3

    assert (workdir / "raw.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "processed.json.count").read_text(encoding="utf-8") == "1"
    assert (workdir / "report.json.count").read_text(encoding="utf-8") == "1"
