import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _run(script: Path, cwd: Path, state_dir: Path, run_key: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    env["LOOMA_RUN_KEY"] = run_key
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def test_same_command_can_have_isolated_active_instances(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import agent, workflow

@workflow
def main():
    agent(task="wait", input={"x": 1}, output_schema=dict)

main()
""",
        encoding="utf-8",
    )

    first_a = _run(script, tmp_path, state_dir, "A")
    first_b = _run(script, tmp_path, state_dir, "B")

    assert first_a.returncode == 75
    assert first_b.returncode == 75

    run_dirs = list((state_dir / "runs").iterdir())
    assert len(run_dirs) == 2

    keys = set()
    for run_dir in run_dirs:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        keys.add(state["invocation"]["run_key"])
        assert state["status"] == "waiting_agent"

    assert keys == {"A", "B"}

    # Re-entering A must resume/re-emit A's existing run, not create a third run.
    second_a = _run(script, tmp_path, state_dir, "A")
    assert second_a.returncode == 75
    assert len(list((state_dir / "runs").iterdir())) == 2


def test_failed_run_releases_active_pointer_and_next_run_starts_clean(tmp_path: Path):
    script = tmp_path / "fails.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import workflow

@workflow
def main():
    raise RuntimeError("boom")

main()
""",
        encoding="utf-8",
    )

    first = _run(script, tmp_path, state_dir, "failure-case")
    assert first.returncode != 0
    assert list((state_dir / "invocations").glob("*.json")) == []

    second = _run(script, tmp_path, state_dir, "failure-case")
    assert second.returncode != 0

    run_dirs = list((state_dir / "runs").iterdir())
    assert len(run_dirs) == 2
    for run_dir in run_dirs:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        assert state["status"] == "failed"


def test_user_system_exit_finalizes_run_and_releases_pointer(tmp_path: Path):
    script = tmp_path / "exit.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
import sys
from looma import workflow

@workflow
def main():
    sys.exit(3)

main()
""",
        encoding="utf-8",
    )

    result = _run(script, tmp_path, state_dir, "system-exit")
    assert result.returncode == 3
    assert list((state_dir / "invocations").glob("*.json")) == []

    run_dir = next((state_dir / "runs").iterdir())
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert "SystemExit" in state["error"]
