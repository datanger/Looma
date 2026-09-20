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
        f'''
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
''',
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
        '''
from looma import workflow, agent

@workflow
def main():
    values = []
    for i in range(2):
        r = agent(task=f"round {i}", input={"i": i}, output_schema=dict)
        values.append(r["v"])
    print("DONE", values)

main()
''',
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

    skill = files("looma").joinpath("skills", "llm-driven-programmatic-coding", "SKILL.md")
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "same-command replay/resume" in text
    assert "script2agent" in text
    assert "agent2script" in text
