from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .exceptions import Agent2ScriptValidationError
from .serde import load_json

AGENT2SCRIPT_ERROR_BEGIN = "<<<AGENT2SCRIPT_ERROR>>>"
AGENT2SCRIPT_ERROR_END = "<<<END_AGENT2SCRIPT_ERROR>>>"
AGENT2SCRIPT_VALIDATION_EXIT_CODE = 76


def validate_agent2script(actual: Any, expected: Any) -> dict:
    """Validate an agent2script response against script2agent.expected_output.

    Validation is intentionally strict. A resume command is accepted only when
    it contains exactly the script and args fields and both values exactly match
    the expected output persisted by the suspended workflow.
    """
    mismatches: list[dict] = []

    if not isinstance(expected, Mapping):
        raise Agent2ScriptValidationError(
            "script2agent.expected_output must be an object.",
            expected=expected,
            actual=actual,
            mismatches=[{"field": "expected_output", "reason": "not_object"}],
        )

    if not isinstance(actual, Mapping):
        raise Agent2ScriptValidationError(
            "agent2script must be a JSON object.",
            expected=dict(expected),
            actual=actual,
            mismatches=[{"field": "agent2script", "reason": "not_object"}],
        )

    expected_keys = {"script", "args"}
    actual_keys = set(actual.keys())
    if actual_keys != expected_keys:
        mismatches.append(
            {
                "field": "keys",
                "expected": sorted(expected_keys),
                "actual": sorted(str(k) for k in actual_keys),
            }
        )

    script = actual.get("script")
    args = actual.get("args")

    if not isinstance(script, str) or not script:
        mismatches.append(
            {"field": "script", "reason": "must_be_non_empty_string", "actual": script}
        )

    if not isinstance(args, list) or not all(isinstance(v, str) for v in args):
        mismatches.append(
            {"field": "args", "reason": "must_be_array_of_strings", "actual": args}
        )

    if script != expected.get("script"):
        mismatches.append(
            {
                "field": "script",
                "expected": expected.get("script"),
                "actual": script,
            }
        )

    if args != expected.get("args"):
        mismatches.append(
            {
                "field": "args",
                "expected": expected.get("args"),
                "actual": args,
            }
        )

    if mismatches:
        raise Agent2ScriptValidationError(
            "Returned agent2script does not exactly match script2agent.expected_output.",
            expected=dict(expected),
            actual=dict(actual),
            mismatches=mismatches,
        )

    return {"script": script, "args": list(args)}


def validate_request_response(request: Mapping[str, Any], response: Any) -> dict:
    expected = request.get("expected_output")
    return validate_agent2script(response, expected)


def _load_response(path: Path) -> Any:
    try:
        return load_json(path)
    except FileNotFoundError as exc:
        raise Agent2ScriptValidationError(
            f"agent2script response file does not exist: {path}",
            mismatches=[{"field": "response_file", "reason": "missing", "actual": str(path)}],
        ) from exc
    except json.JSONDecodeError as exc:
        raise Agent2ScriptValidationError(
            f"agent2script response file is not valid JSON: {path}",
            mismatches=[{"field": "response_file", "reason": "invalid_json", "actual": str(path)}],
        ) from exc


def _state_for_request(request_file: Path) -> dict | None:
    state_file = request_file.parent.parent / "state.json"
    if not state_file.exists():
        return None
    try:
        return load_json(state_file)
    except Exception:
        return None


def _ensure_agent_result_exists(request: Mapping[str, Any]) -> Path:
    output = request.get("output")
    if not isinstance(output, Mapping):
        raise Agent2ScriptValidationError(
            "script2agent.output must be an object before resume.",
            mismatches=[{"field": "output", "reason": "not_object"}],
        )
    result_file = output.get("result_file")
    if not isinstance(result_file, str) or not result_file:
        raise Agent2ScriptValidationError(
            "script2agent.output.result_file is missing.",
            mismatches=[{"field": "output.result_file", "reason": "missing"}],
        )
    path = Path(result_file)
    if not path.exists():
        raise Agent2ScriptValidationError(
            "Agent result is missing; refusing to resume the workflow.",
            mismatches=[
                {"field": "output.result_file", "reason": "missing", "actual": str(path)}
            ],
        )
    try:
        load_json(path)
    except json.JSONDecodeError as exc:
        raise Agent2ScriptValidationError(
            "Agent result file is not valid JSON; refusing to resume the workflow.",
            mismatches=[
                {"field": "output.result_file", "reason": "invalid_json", "actual": str(path)}
            ],
        ) from exc
    return path


def execute_validated_agent2script(
    *,
    request_file: str | Path,
    response_file: str | Path,
) -> int:
    """Validate a host Agent response, then execute only the expected command."""
    request_path = Path(request_file).resolve()
    response_path = Path(response_file).resolve()
    request = load_json(request_path)
    response = _load_response(response_path)

    validated = validate_request_response(request, response)
    _ensure_agent_result_exists(request)

    state = _state_for_request(request_path)
    cwd = None
    if state:
        invocation = state.get("invocation")
        if isinstance(invocation, Mapping):
            value = invocation.get("cwd")
            if isinstance(value, str) and value:
                cwd = value

    command: Sequence[str] = [validated["script"], *validated["args"]]
    completed = subprocess.run(command, cwd=cwd)
    return completed.returncode


def format_agent2script_error(error: Agent2ScriptValidationError) -> str:
    payload = json.dumps(error.as_dict(), ensure_ascii=False, indent=2)
    return f"{AGENT2SCRIPT_ERROR_BEGIN}\n{payload}\n{AGENT2SCRIPT_ERROR_END}"
