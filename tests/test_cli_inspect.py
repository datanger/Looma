import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def test_inspect_shows_pending_agent_contract(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import agent, workflow

@workflow
def main():
    agent(task="inspect me", input={"value": 3}, output_schema=dict)

main()
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    env["LOOMA_RUN_KEY"] = "inspect-case"

    first = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 75

    inspected = subprocess.run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "--state-dir",
            str(state_dir),
            "inspect",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert inspected.returncode == 0, inspected.stderr

    payload = json.loads(inspected.stdout)
    assert payload["status"] == "waiting_agent"
    assert payload["invocation"]["run_key"] == "inspect-case"
    assert payload["pending_request"]["request_file"].endswith("-script2agent.json")
    assert payload["pending_request"]["result_file"].endswith("-agent-result.json")
    assert payload["pending_request"]["expected_output"]["script"] == sys.executable
    assert payload["events"][-1]["kind"] == "agent"

    inspected_by_id = subprocess.run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "--state-dir",
            str(state_dir),
            "inspect",
            payload["run_id"],
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert inspected_by_id.returncode == 0
    assert json.loads(inspected_by_id.stdout)["run_id"] == payload["run_id"]
