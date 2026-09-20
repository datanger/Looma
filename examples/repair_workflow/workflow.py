"""Meaningful AEP example: repair a broken Python project until tests pass."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from looma import agent, step, workflow


HERE = Path(__file__).resolve().parent


@dataclass
class RepairResult:
    changed: bool
    summary: str
    analysis_tracks: list[str]


def run_json_script(script: str, *args: str):
    completed = subprocess.run(
        [sys.executable, script, *args],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script} failed with {completed.returncode}: {completed.stderr}"
        )

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script} did not return JSON. stdout={completed.stdout!r}"
        ) from exc


@workflow
def repair_until_green(workdir: str, max_repairs: int = 3):
    root = Path(workdir).resolve()
    report_file = root / "repair-report.json"

    workspace = step(
        run_json_script,
        str(HERE / "prepare_workspace.py"),
        "--workdir",
        str(root),
    )
    repo = workspace["repo"]

    repair_rounds = 0
    final_check = None

    # max_repairs repair opportunities plus one final validation pass.
    for check_index in range(max_repairs + 1):
        final_check = step(
            run_json_script,
            str(HERE / "run_checks.py"),
            "--repo",
            repo,
            "--attempt",
            str(check_index + 1),
        )

        if final_check["passed"]:
            return step(
                run_json_script,
                str(HERE / "build_report.py"),
                "--repo",
                repo,
                "--status",
                "passed",
                "--repair-rounds",
                str(repair_rounds),
                "--check-json",
                json.dumps(final_check, ensure_ascii=False),
                "--output",
                str(report_file),
            )

        if repair_rounds >= max_repairs:
            break

        agent(
            task=(
                "修复 input.repo 中导致当前测试失败的代码。"
                "请直接使用当前宿主 Coding Agent 的原生文件与终端工具修改该 workspace。"
                "为了加快分析，如果宿主支持 native subagent，请将以下三个彼此独立的分析方向并发执行："
                "(1) root-cause analysis：定位失败测试对应的代码根因；"
                "(2) test-contract review：确认测试真正要求的行为，避免为了过测试而破坏语义；"
                "(3) regression-risk review：检查修复可能影响的其他行为。"
                "主宿主 Agent 在 gather 后负责最终修改代码。"
                "不得通过 CLI、SDK、API 或 subprocess 启动另一个 Coding Agent；"
                "subagent 并发只能使用当前宿主自身的原生能力。"
                "修改完成后返回结构化修复摘要。"
            ),
            input={
                "repo": repo,
                "repair_round": repair_rounds + 1,
                "check": final_check,
            },
            output_schema=RepairResult,
        )
        repair_rounds += 1

    assert final_check is not None
    return step(
        run_json_script,
        str(HERE / "build_report.py"),
        "--repo",
        repo,
        "--status",
        "failed",
        "--repair-rounds",
        str(repair_rounds),
        "--check-json",
        json.dumps(final_check, ensure_ascii=False),
        "--output",
        str(report_file),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--max-repairs", type=int, default=3)
    args = parser.parse_args()

    result = repair_until_green(args.workdir, args.max_repairs)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
