"""Fault-injection benchmark for Looma's Agent boundary contracts."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from experiments.common import (
    latest_run,
    looma_env,
    only_request,
    read_json,
    run_python,
    write_json,
)


WORKFLOW = r'''
from dataclasses import dataclass
from pathlib import Path
from looma import agent, step, workflow

@dataclass
class Decision:
    choice: str

def mark_done(path):
    Path(path).write_text("done", encoding="utf-8")
    return {"done": True}

@workflow
def main():
    decision = agent(
        task="choose",
        input={"value": 1},
        output_schema=Decision,
    )
    step(mark_done, {sentinel!r})
    print("DONE", decision.choice)

main()
'''


INVALID_CASES = {
    "invalid_input_schema",
    "missing_result",
    "malformed_result",
    "wrong_result_schema",
    "wrong_resume_script",
    "wrong_resume_args",
    "extra_resume_field",
    "replay_mismatch",
}
ALL_CASES = ["valid", *sorted(INVALID_CASES)]


def prepare_case(root: Path) -> tuple[Path, Path, Path, dict[str, str], dict]:
    state_dir = root / "state"
    sentinel = root / "done.txt"
    script = root / "workflow.py"
    script.write_text(WORKFLOW.replace("{sentinel!r}", repr(str(sentinel))), encoding="utf-8")
    env = looma_env(state_dir)

    first = run_python([script], cwd=root, env=env)
    if first.returncode != 75:
        raise RuntimeError(f"initial workflow failed: {first.stderr or first.stdout}")

    run_dir = latest_run(state_dir)
    request_file = only_request(run_dir)
    request = read_json(request_file)
    return script, sentinel, request_file, env, request


def run_invalid_input_case(root: Path) -> dict:
    state_dir = root / "state"
    sentinel = root / "done.txt"
    script = root / "invalid_input.py"
    script.write_text(
        f"""
from pathlib import Path
from looma import agent, workflow

@workflow
def main():
    agent(
        task="validate input",
        input={{"limit": "five"}},
        input_schema={{
            "type": "object",
            "required": ["limit"],
            "properties": {{"limit": {{"type": "integer"}}}},
            "additionalProperties": False,
        }},
        output_schema=dict,
    )
    Path({str(sentinel)!r}).write_text("done", encoding="utf-8")

main()
""",
        encoding="utf-8",
    )
    env = looma_env(state_dir)
    result = run_python([script], cwd=root, env=env)
    request_files = list(state_dir.glob("runs/*/events/*-script2agent.json"))
    passed = (
        result.returncode != 0
        and not sentinel.exists()
        and not request_files
        and "AgentInputValidationError" in result.stderr
    )
    return {
        "case": "invalid_input_schema",
        "expected_accept": False,
        "returncode": result.returncode,
        "accepted": False,
        "sentinel_exists": sentinel.exists(),
        "passed": passed,
        "stdout_tail": result.stdout[-500:],
        "stderr_tail": result.stderr[-500:],
    }


def run_case(case: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"looma-fault-{case}-") as raw:
        root = Path(raw)
        if case == "invalid_input_schema":
            return run_invalid_input_case(root)

        script, sentinel, request_file, env, request = prepare_case(root)
        result_file = Path(request["output"]["result_file"])
        response = dict(request["expected_output"])

        if case == "missing_result":
            pass
        elif case == "malformed_result":
            result_file.write_text("{not-json", encoding="utf-8")
        elif case == "wrong_result_schema":
            write_json(result_file, {"choice": 42})
        else:
            write_json(result_file, {"choice": "A"})

        if case == "wrong_resume_script":
            response["script"] = str(root / "not-the-expected-script")
        elif case == "wrong_resume_args":
            response["args"] = [*response["args"], "--unexpected"]
        elif case == "extra_resume_field":
            response["reasoning"] = "this field is forbidden"
        elif case == "replay_mismatch":
            text = script.read_text(encoding="utf-8")
            script.write_text(text.replace('task="choose"', 'task="changed"'), encoding="utf-8")

        response_file = root / "agent2script.json"
        write_json(response_file, response)

        result = run_python(
            [
                "-m",
                "looma.cli",
                "handoff",
                "--request",
                request_file,
                "--response",
                response_file,
            ],
            cwd=root,
            env=env,
        )

        sentinel_exists = sentinel.exists()
        accepted = result.returncode == 0
        expected_accept = case == "valid"
        passed = (
            accepted
            and sentinel_exists
            if expected_accept
            else (not accepted and not sentinel_exists)
        )

        return {
            "case": case,
            "expected_accept": expected_accept,
            "returncode": result.returncode,
            "accepted": accepted,
            "sentinel_exists": sentinel_exists,
            "passed": passed,
            "stdout_tail": result.stdout[-500:],
            "stderr_tail": result.stderr[-500:],
        }


def parse_cases(value: str) -> list[str]:
    cases = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in cases if item not in ALL_CASES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown cases: {', '.join(unknown)}")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=parse_cases, default=ALL_CASES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = [run_case(case) for case in args.cases]
    invalid = [row for row in rows if not row["expected_accept"]]
    payload = {
        "benchmark": "looma-contract-fault-injection",
        "cases": rows,
        "summary": {
            "cases": len(rows),
            "passed": sum(bool(row["passed"]) for row in rows),
            "invalid_cases": len(invalid),
            "invalid_detected": sum(not row["accepted"] for row in invalid),
            "false_acceptances": sum(row["accepted"] for row in invalid),
            "valid_completions": sum(
                row["accepted"] and row["sentinel_exists"]
                for row in rows
                if row["expected_accept"]
            ),
        },
    }

    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)

    return 0 if all(row["passed"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
