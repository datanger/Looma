"""Compose multiple standalone scripts and a host Agent into one Looma workflow."""

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
class ReportDecision:
    mode: str
    reason: str


def run_script(script: str, *args: str):
    completed = subprocess.run(
        [sys.executable, script, *args],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script} failed with {completed.returncode}: {completed.stderr}"
        )
    return {
        "script": script,
        "args": list(args),
        "stdout": completed.stdout.strip(),
    }


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@workflow
def pipeline(workdir: str):
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    raw = root / "raw.json"
    processed = root / "processed.json"
    report = root / "report.json"

    step(
        run_script,
        str(HERE / "collect.py"),
        "--output",
        str(raw),
    )

    step(
        run_script,
        str(HERE / "transform.py"),
        "--input",
        str(raw),
        "--output",
        str(processed),
    )

    metrics = step(load_json, str(processed))

    decision = agent(
        task=(
            "根据 metrics 选择报告模式。mode 只能是 summary 或 detailed。"
            "如果指标足够简单可以 summary，否则 detailed。"
            "返回 JSON：{\"mode\": str, \"reason\": str}。"
        ),
        input=metrics,
        output_schema=ReportDecision,
    )

    step(
        run_script,
        str(HERE / "report.py"),
        "--input",
        str(processed),
        "--output",
        str(report),
        "--mode",
        decision.mode,
    )

    return step(load_json, str(report))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    print(json.dumps(pipeline(args.workdir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
