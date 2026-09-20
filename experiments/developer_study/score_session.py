from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


METHODS = {
    "direct_sdk",
    "langgraph",
    "microsoft_agent_framework",
    "looma",
}


def sus_score(responses: list[int]) -> float:
    if len(responses) != 10:
        raise ValueError("SUS requires exactly 10 responses")
    if any(value < 1 or value > 5 for value in responses):
        raise ValueError("SUS responses must be integers in [1, 5]")

    contribution = 0
    for index, value in enumerate(responses):
        if index % 2 == 0:
            contribution += value - 1
        else:
            contribution += 5 - value
    return contribution * 2.5


def validate_session(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "participant_id",
        "task_id",
        "method",
        "started_at",
        "ended_at",
        "elapsed_seconds",
        "tests_passed",
        "implementation_sloc",
        "debug_iterations",
        "documentation_lookups",
        "external_help_events",
        "sus_responses",
    ]
    for name in required:
        if name not in value:
            errors.append(f"missing required field: {name}")

    if value.get("method") not in METHODS:
        errors.append(f"unsupported method: {value.get('method')}")

    for name in (
        "elapsed_seconds",
        "implementation_sloc",
        "debug_iterations",
        "documentation_lookups",
        "external_help_events",
    ):
        raw = value.get(name)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
            errors.append(f"{name} must be a non-negative number")

    if not isinstance(value.get("tests_passed"), bool):
        errors.append("tests_passed must be boolean")

    responses = value.get("sus_responses")
    if not isinstance(responses, list):
        errors.append("sus_responses must be a list")
    else:
        try:
            sus_score(responses)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    value = json.loads(args.session.read_text(encoding="utf-8"))
    errors = validate_session(value)
    if errors:
        print(json.dumps({"status": "invalid", "errors": errors}, indent=2))
        return 2

    scored = dict(value)
    scored["sus_score"] = round(sus_score(value["sus_responses"]), 2)
    scored["status"] = "valid"

    encoded = json.dumps(scored, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
