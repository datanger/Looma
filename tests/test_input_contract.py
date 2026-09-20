import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from looma import AgentInputValidationError
from looma.runtime import WorkflowRuntime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


INPUT_SCHEMA = {
    "type": "object",
    "required": ["query", "limit"],
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "limit": {"type": "integer"},
    },
    "additionalProperties": False,
}


def test_runtime_rejects_invalid_agent_input_before_suspend(tmp_path: Path):
    runtime = WorkflowRuntime(
        workflow_name="tests.input_contract",
        source_function="main",
        state_root=tmp_path / "state",
    )

    with pytest.raises(AgentInputValidationError) as exc_info:
        runtime.agent(
            task="research",
            input={"query": "", "limit": "five"},
            input_schema=INPUT_SCHEMA,
            output_schema=dict,
        )

    error = exc_info.value.as_dict()
    assert error["error"] == "agent_input_validation_error"
    assert error["actual_input"]["limit"] == "five"
    assert any(item["path"] == "$.query" for item in error["mismatches"])
    assert any(item["path"] == "$.limit" for item in error["mismatches"])
    assert runtime.state["events"] == []


def test_script2agent_contains_declared_input_schema(tmp_path: Path, monkeypatch):
    script = tmp_path / "input_contract_demo.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import workflow, agent

INPUT_SCHEMA = {
    "type": "object",
    "required": ["query", "limit"],
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "additionalProperties": False,
}

@workflow
def main():
    agent(
        task="research",
        input={"query": "AEP", "limit": 3},
        input_schema=INPUT_SCHEMA,
        output_schema={"type": "object"},
    )

main()
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 75, completed.stderr

    run_dir = next((state_dir / "runs").iterdir())
    request_file = next((run_dir / "events").glob("*-script2agent.json"))
    request = json.loads(request_file.read_text(encoding="utf-8"))
    assert request["output"]["agent_input"] == {"query": "AEP", "limit": 3}
    assert request["output"]["input_schema"] == INPUT_SCHEMA


def test_agent_without_input_schema_remains_backward_compatible(tmp_path: Path):
    runtime = WorkflowRuntime(
        workflow_name="tests.no_input_contract",
        source_function="main",
        state_root=tmp_path / "state",
    )
    from looma.exceptions import WorkflowSuspend

    with pytest.raises(WorkflowSuspend) as exc_info:
        runtime.agent(
            task="legacy",
            input={"anything": ["json", 1]},
            output_schema=dict,
        )
    assert "input_schema" not in exc_info.value.request["output"]
