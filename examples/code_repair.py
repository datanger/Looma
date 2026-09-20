"""Software-engineering pattern: run tests, let the host Agent repair code, then test again."""

import subprocess
import sys
from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class RepairResult:
    changed: bool
    summary: str


def run_tests(repo: str):
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    }


@workflow
def repair_until_green(repo: str = ".", max_attempts: int = 3):
    for attempt in range(max_attempts):
        test_result = step(run_tests, repo)

        if test_result["returncode"] == 0:
            return {"status": "passed", "attempts": attempt, "tests": test_result}

        agent(
            task=(
                "分析 pytest 失败原因，并直接使用当前 Coding Agent 宿主的文件/代码工具修复仓库。"
                "不要伪造测试结果。完成修改后返回 JSON："
                "{\"changed\": bool, \"summary\": str}。"
            ),
            input={
                "repo": repo,
                "attempt": attempt,
                "test_result": test_result,
            },
            output_schema=RepairResult,
        )

    final_result = step(run_tests, repo)
    return {
        "status": "passed" if final_result["returncode"] == 0 else "failed",
        "attempts": max_attempts,
        "tests": final_result,
    }


if __name__ == "__main__":
    print(repair_until_green())
