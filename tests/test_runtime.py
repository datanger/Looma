import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def run_script(script: Path, cwd: Path, state_dir: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def latest_run(state_dir: Path) -> Path:
    runs = sorted((state_dir / "runs").iterdir(), key=lambda p: p.stat().st_mtime)
    assert runs
    return runs[-1]


def test_suspend_then_same_command_resume(tmp_path: Path):
    script = tmp_path / "demo.py"
    state_dir = tmp_path / "state"
    side_effect = tmp_path / "counter.txt"
    script.write_text(
        f"""
from dataclasses import dataclass
from pathlib import Path
from looma import workflow, step, agent

@dataclass
class Decision:
    choice: str

def once():
    p = Path({str(side_effect)!r})
    n = int(p.read_text() or "0") if p.exists() else 0
    p.write_text(str(n + 1))
    return {{"n": n + 1}}

@workflow
def main():
    x = step(once)
    d = agent(task="choose", input=x, output_schema=Decision)
    print("FINAL", d.choice, x["n"])

main()
""",
        encoding="utf-8",
    )

    first = run_script(script, tmp_path, state_dir)
    assert first.returncode == 75
    assert "<<<SCRIPT2AGENT>>>" in first.stdout
    assert side_effect.read_text() == "1"

    run_dir = latest_run(state_dir)
    request = json.loads((run_dir / "events" / "0001-script2agent.json").read_text(encoding="utf-8"))
    assert request["expected_output"]["script"] == sys.executable
    assert request["expected_output"]["args"][0] == str(script)

    result_file = Path(request["output"]["result_file"])
    result_file.write_text('{"choice":"A"}', encoding="utf-8")

    second = run_script(script, tmp_path, state_dir)
    assert second.returncode == 0, second.stderr
    assert "FINAL A 1" in second.stdout
    assert side_effect.read_text() == "1", "step() must not repeat the side effect on replay"


def test_two_agent_calls_across_restarts(tmp_path: Path):
    script = tmp_path / "loop.py"
    state_dir = tmp_path / "state"
    script.write_text(
        """
from looma import workflow, agent

@workflow
def main():
    values = []
    for i in range(2):
        r = agent(task=f"round {i}", input={"i": i}, output_schema=dict)
        values.append(r["v"])
    print("DONE", values)

main()
""",
        encoding="utf-8",
    )

    first = run_script(script, tmp_path, state_dir)
    assert first.returncode == 75
    run_dir = latest_run(state_dir)
    req0 = json.loads((run_dir / "events" / "0000-script2agent.json").read_text(encoding="utf-8"))
    Path(req0["output"]["result_file"]).write_text('{"v":10}', encoding="utf-8")

    second = run_script(script, tmp_path, state_dir)
    assert second.returncode == 75
    req1 = json.loads((run_dir / "events" / "0001-script2agent.json").read_text(encoding="utf-8"))
    Path(req1["output"]["result_file"]).write_text('{"v":20}', encoding="utf-8")

    third = run_script(script, tmp_path, state_dir)
    assert third.returncode == 0, third.stderr
    assert "DONE [10, 20]" in third.stdout


def test_fixed_prompt_is_exact():
    from looma.protocol import FIXED_PROMPT

    assert FIXED_PROMPT == (
        "通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；"
        "task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 "
        "agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；"
        "完成后仅按 expected_output 返回。"
    )


def test_skill_is_packaged():
    from importlib.resources import files

    skill = files("looma").joinpath("skills", "agent-embedded-programming", "SKILL.md")
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "Agent-Embedded Programming" in text
    assert "script2agent" in text
    assert "agent2script" in text
    assert "same-command replay/resume" in text


def test_agent2script_exact_match_validation():
    from looma import validate_agent2script

    expected = {
        "script": "/usr/bin/python3",
        "args": ["/project/main.py", "--input", "data.json"],
    }
    actual = {
        "script": "/usr/bin/python3",
        "args": ["/project/main.py", "--input", "data.json"],
    }

    assert validate_agent2script(actual, expected) == expected


def test_agent2script_mismatch_is_rejected():
    import pytest
    from looma import Agent2ScriptValidationError, validate_agent2script

    expected = {
        "script": "/usr/bin/python3",
        "args": ["/project/main.py"],
    }
    actual = {
        "script": "/usr/bin/python3",
        "args": ["/project/other.py"],
    }

    with pytest.raises(Agent2ScriptValidationError) as exc_info:
        validate_agent2script(actual, expected)

    error = exc_info.value.as_dict()
    assert error["error"] == "agent2script_validation_error"
    assert error["expected_output"] == expected
    assert error["actual_output"] == actual
    assert any(item["field"] == "args" for item in error["mismatches"])


def test_agent2script_extra_fields_are_rejected():
    import pytest
    from looma import Agent2ScriptValidationError, validate_agent2script

    expected = {"script": "python", "args": ["main.py"]}
    actual = {
        "script": "python",
        "args": ["main.py"],
        "reasoning": "I changed nothing",
    }

    with pytest.raises(Agent2ScriptValidationError):
        validate_agent2script(actual, expected)


def test_guarded_handoff_does_not_execute_mismatched_command(tmp_path: Path):
    from looma.handoff import execute_validated_agent2script
    from looma import Agent2ScriptValidationError

    run_dir = tmp_path / "runs" / "run-1"
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True)

    sentinel = tmp_path / "should-not-exist.txt"
    expected_script = tmp_path / "expected.py"
    wrong_script = tmp_path / "wrong.py"

    expected_script.write_text("print('expected')", encoding="utf-8")
    wrong_script.write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')",
        encoding="utf-8",
    )

    result_file = events_dir / "0000-agent-result.json"
    result_file.write_text('{"ok": true}', encoding="utf-8")

    request_file = events_dir / "0000-script2agent.json"
    request_file.write_text(
        json.dumps(
            {
                "output": {"result_file": str(result_file)},
                "expected_output": {
                    "script": sys.executable,
                    "args": [str(expected_script)],
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps({"invocation": {"cwd": str(tmp_path)}}),
        encoding="utf-8",
    )

    response_file = tmp_path / "agent2script.json"
    response_file.write_text(
        json.dumps(
            {
                "script": sys.executable,
                "args": [str(wrong_script)],
            }
        ),
        encoding="utf-8",
    )

    try:
        execute_validated_agent2script(
            request_file=request_file,
            response_file=response_file,
        )
        raise AssertionError("mismatched agent2script should have been rejected")
    except Agent2ScriptValidationError:
        pass

    assert not sentinel.exists(), "A mismatched Agent command must never be executed"


def test_guarded_handoff_executes_only_validated_command(tmp_path: Path):
    from looma.handoff import execute_validated_agent2script

    run_dir = tmp_path / "runs" / "run-1"
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True)

    sentinel = tmp_path / "executed.txt"
    script = tmp_path / "resume_target.py"
    script.write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('ok')",
        encoding="utf-8",
    )

    result_file = events_dir / "0000-agent-result.json"
    result_file.write_text('{"ok": true}', encoding="utf-8")

    expected = {"script": sys.executable, "args": [str(script)]}
    request_file = events_dir / "0000-script2agent.json"
    request_file.write_text(
        json.dumps(
            {
                "output": {"result_file": str(result_file)},
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


def test_cli_handoff_rejects_wrong_command_then_resumes_exact_workflow(tmp_path: Path):
    script = tmp_path / "workflow.py"
    state_dir = tmp_path / "state"
    wrong_side_effect = tmp_path / "wrong-command-executed.txt"

    script.write_text(
        """
from dataclasses import dataclass
from looma import workflow, agent

@dataclass
class Decision:
    choice: str

@workflow
def main():
    decision = agent(
        task="choose A",
        input={"value": 1},
        output_schema=Decision,
    )
    print("FINAL", decision.choice)

main()
""",
        encoding="utf-8",
    )

    first = run_script(script, tmp_path, state_dir)
    assert first.returncode == 75

    run_dir = latest_run(state_dir)
    request_file = run_dir / "events" / "0000-script2agent.json"
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        '{"choice":"A"}',
        encoding="utf-8",
    )

    wrong_script = tmp_path / "wrong.py"
    wrong_script.write_text(
        f"from pathlib import Path; Path({str(wrong_side_effect)!r}).write_text('bad')",
        encoding="utf-8",
    )
    response_file = tmp_path / "agent2script.json"
    response_file.write_text(
        json.dumps(
            {
                "script": sys.executable,
                "args": [str(wrong_script)],
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)

    rejected = subprocess.run(
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

    assert rejected.returncode == 76
    assert "<<<AGENT2SCRIPT_ERROR>>>" in rejected.stdout
    assert "expected_output" in rejected.stdout
    assert "actual_output" in rejected.stdout
    assert not wrong_side_effect.exists()

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
    assert "FINAL A" in resumed.stdout
    assert not wrong_side_effect.exists()


def test_cli_handoff_refuses_resume_without_agent_result(tmp_path: Path):
    run_dir = tmp_path / "runs" / "run-1"
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True)

    target = tmp_path / "target.py"
    sentinel = tmp_path / "executed.txt"
    target.write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')",
        encoding="utf-8",
    )

    expected = {
        "script": sys.executable,
        "args": [str(target)],
    }
    missing_result = events_dir / "0000-agent-result.json"
    request_file = events_dir / "0000-script2agent.json"
    request_file.write_text(
        json.dumps(
            {
                "output": {"result_file": str(missing_result)},
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

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)

    result = subprocess.run(
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

    assert result.returncode == 76
    assert "Agent result is missing" in result.stdout
    assert not sentinel.exists()
