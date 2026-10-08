import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
EXAMPLE = PROJECT_ROOT / "examples" / "gepa_optimization" / "workflow.py"


def _env(state_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    return env


def test_gepa_example_suspends_and_resumes_without_repeating_evaluation(tmp_path: Path):
    state_dir = tmp_path / "state"
    env = _env(state_dir)
    first = subprocess.run(
        [sys.executable, str(EXAMPLE)],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert first.returncode == 75
    run_dir = next((state_dir / "runs").iterdir())
    request_file = next((run_dir / "events").glob("*-script2agent.json"))
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        json.dumps(
            {
                "candidate": {
                    "instruction": "Answer directly and cite evidence.",
                },
                "components_to_update": ["instruction"],
                "rationale": "The trace showed that evidence was missing.",
                "hypothesis": "Evidence guidance will improve the score.",
                "targeted_failure": "missing evidence",
            }
        ),
        encoding="utf-8",
    )
    response_file = tmp_path / "agent2script.json"
    response_file.write_text(json.dumps(request["expected_output"]), encoding="utf-8")

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
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert resumed.returncode == 0, resumed.stderr
    assert '"accepted": true' in resumed.stdout
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    accepted = json.loads(
        Path(state["events"][-1]["result_file"]).read_text(encoding="utf-8")
    )
    assert "evidence-question-1" in accepted["state"]["frontier"]["instance_winners"]
    assert [event["kind"] for event in state["events"]] == [
        "step",
        "agent",
        "step",
        "step",
    ]
