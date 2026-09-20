from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from looma import AgentResultValidationError
from looma.handoff import execute_validated_agent2script
from looma.protocol import describe_schema


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


@dataclass
class Decision:
    choice: str
    score: int
    note: str | None = None


def test_dataclass_output_schema_is_structural_json_schema():
    schema = describe_schema(Decision)

    assert schema["type"] == "object"
    assert schema["properties"]["choice"] == {"type": "string"}
    assert schema["properties"]["score"] == {"type": "integer"}
    assert schema["properties"]["note"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert schema["required"] == ["choice", "score"]
    assert schema["additionalProperties"] is False


def test_handoff_rejects_result_that_violates_output_schema(tmp_path: Path):
    run_dir = tmp_path / "runs" / "run-1"
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True)

    sentinel = tmp_path / "must-not-run.txt"
    target = tmp_path / "resume.py"
    target.write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')",
        encoding="utf-8",
    )

    result_file = events_dir / "0000-agent-result.json"
    result_file.write_text('{"choice": 123}', encoding="utf-8")

    expected = {"script": sys.executable, "args": [str(target)]}
    request_file = events_dir / "0000-script2agent.json"
    request_file.write_text(
        json.dumps(
            {
                "output": {
                    "result_file": str(result_file),
                    "output_schema": {
                        "type": "object",
                        "properties": {"choice": {"type": "string"}},
                        "required": ["choice"],
                        "additionalProperties": False,
                    },
                },
                "expected_output": expected,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps({"invocation": {"cwd": str(tmp_path)}}),
        encoding="utf-8",
    )

    response_file = tmp_path / "agent2script.json"
    response_file.write_text(json.dumps(expected), encoding="utf-8")

    with pytest.raises(AgentResultValidationError) as exc_info:
        execute_validated_agent2script(
            request_file=request_file,
            response_file=response_file,
        )

    payload = exc_info.value.as_dict()
    assert payload["error"] == "agent_result_validation_error"
    assert any(item["path"] == "$.choice" for item in payload["mismatches"])
    assert not sentinel.exists()


def test_handoff_executes_after_result_schema_validation(tmp_path: Path):
    run_dir = tmp_path / "runs" / "run-1"
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True)

    sentinel = tmp_path / "executed.txt"
    target = tmp_path / "resume.py"
    target.write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('ok')",
        encoding="utf-8",
    )

    result_file = events_dir / "0000-agent-result.json"
    result_file.write_text('{"choice": "A"}', encoding="utf-8")

    expected = {"script": sys.executable, "args": [str(target)]}
    request_file = events_dir / "0000-script2agent.json"
    request_file.write_text(
        json.dumps(
            {
                "output": {
                    "result_file": str(result_file),
                    "output_schema": {
                        "type": "object",
                        "properties": {"choice": {"type": "string"}},
                        "required": ["choice"],
                        "additionalProperties": False,
                    },
                },
                "expected_output": expected,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps({"invocation": {"cwd": str(tmp_path)}}),
        encoding="utf-8",
    )

    response_file = tmp_path / "agent2script.json"
    response_file.write_text(json.dumps(expected), encoding="utf-8")

    code = execute_validated_agent2script(
        request_file=request_file,
        response_file=response_file,
    )

    assert code == 0
    assert sentinel.read_text(encoding="utf-8") == "ok"


def test_direct_resume_still_rejects_invalid_mapping_result(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import agent, workflow

@workflow
def main():
    result = agent(
        task="return a string choice",
        input={"x": 1},
        output_schema={
            "type": "object",
            "properties": {"choice": {"type": "string"}},
            "required": ["choice"],
            "additionalProperties": False,
        },
    )
    print(result)

main()
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)

    first = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 75

    run_dir = next((state_dir / "runs").iterdir())
    request_file = next((run_dir / "events").glob("*-script2agent.json"))
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        '{"choice": 7}',
        encoding="utf-8",
    )

    bypass = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert bypass.returncode != 0
    assert "does not satisfy output_schema" in bypass.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
