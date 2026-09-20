"""A → Agent → B → Agent → C → D/E multi-stage Looma workflow."""

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
class StrategyDecision:
    strategy: str
    reason: str


@dataclass
class ReviewDecision:
    approved: bool
    route: str
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
    return {"script": script, "args": list(args), "stdout": completed.stdout.strip()}


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@workflow
def pipeline(workdir: str):
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    prepared = root / "prepared.json"
    analysis = root / "analysis.json"
    gate = root / "gate.json"
    final = root / "final.json"

    # Stage A
    step(run_script, str(HERE / "prepare.py"), "--output", str(prepared))
    prepared_data = step(load_json, str(prepared))

    # Agent #1 chooses how Stage B should run.
    strategy = agent(
        task=(
            "选择分析策略。strategy 只能是 conservative 或 aggressive。"
            "结合输入数据给出选择，并返回 JSON："
            '{"strategy": str, "reason": str}。'
        ),
        input=prepared_data,
        output_schema=StrategyDecision,
    )

    # Stage B
    step(
        run_script,
        str(HERE / "analyze.py"),
        "--input",
        str(prepared),
        "--output",
        str(analysis),
        "--strategy",
        strategy.strategy,
    )
    analysis_data = step(load_json, str(analysis))

    # Agent #2 reviews Stage B and chooses the desired report route.
    review = agent(
        task=(
            "审核 analysis。返回 approved 和 route。"
            "route 只能是 summary 或 detailed。"
            "返回 JSON：{\"approved\": bool, \"route\": str, \"reason\": str}。"
        ),
        input=analysis_data,
        output_schema=ReviewDecision,
    )

    # Stage C converts Agent intent into a deterministic, validated route.
    step(
        run_script,
        str(HERE / "gate.py"),
        "--analysis",
        str(analysis),
        "--output",
        str(gate),
        "--route",
        review.route,
        "--approved",
        "true" if review.approved else "false",
    )
    gate_data = step(load_json, str(gate))

    # Ordinary Python owns the final branch.
    if gate_data["route"] == "summary":
        step(
            run_script,
            str(HERE / "summary_report.py"),
            "--analysis",
            str(analysis),
            "--gate",
            str(gate),
            "--output",
            str(final),
        )
    else:
        step(
            run_script,
            str(HERE / "detailed_report.py"),
            "--analysis",
            str(analysis),
            "--gate",
            str(gate),
            "--output",
            str(final),
        )

    return step(load_json, str(final))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    print(json.dumps(pipeline(args.workdir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
