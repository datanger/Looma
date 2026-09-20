from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from experiments.workloads.adaptive_evidence.shared.workload import DEFAULT_SCENARIOS, evaluate_report, load_all_scenarios


ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
IMPLEMENTATIONS = {
    "direct_sdk": [sys.executable, str(BASE / "direct_sdk" / "workflow.py")],
    "langgraph": [sys.executable, str(BASE / "langgraph" / "workflow.py")],
    "microsoft_agent_framework": [sys.executable, str(BASE / "microsoft_agent_framework" / "workflow.py")],
    "looma": [sys.executable, str(BASE / "looma" / "host_driver.py")],
}


def run_one(method: str, scenario: dict, repeat: int, root: Path) -> dict:
    output = root / f"{method}-{scenario['id']}-{repeat}.json"
    command = [*IMPLEMENTATIONS[method], "--scenario", scenario["id"], "--output", str(output)]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "src")
    started = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if result.returncode != 0:
        return {
            "method": method, "scenario_id": scenario["id"], "repeat": repeat,
            "returncode": result.returncode, "elapsed_ms": round(elapsed_ms, 3),
            "task_success": False, "error": (result.stderr or result.stdout)[-1000:],
        }
    report = json.loads(output.read_text(encoding="utf-8"))
    quality = evaluate_report(scenario, report)
    return {
        "method": method, "scenario_id": scenario["id"], "repeat": repeat,
        "returncode": 0, "elapsed_ms": round(elapsed_ms, 3),
        "research_rounds": report["research_rounds"],
        "analysis_rounds": report["analysis_rounds"], **quality,
    }


def aggregate(rows: list[dict]) -> list[dict]:
    output = []
    for method in IMPLEMENTATIONS:
        group = [row for row in rows if row["method"] == method]
        if not group:
            continue
        output.append({
            "method": method,
            "runs": len(group),
            "task_success_rate": round(sum(bool(row.get("task_success")) for row in group) / len(group), 4),
            "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in group), 3),
            "mean_research_rounds": round(statistics.mean(row.get("research_rounds", 0) for row in group), 3),
            "mean_analysis_rounds": round(statistics.mean(row.get("analysis_rounds", 0) for row in group), 3),
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", default=",".join(IMPLEMENTATIONS))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    methods = [item.strip() for item in args.methods.split(",") if item.strip()]
    unknown = [item for item in methods if item not in IMPLEMENTATIONS]
    if unknown:
        parser.error(f"unknown methods: {', '.join(unknown)}")
    scenarios = load_all_scenarios(DEFAULT_SCENARIOS)
    with tempfile.TemporaryDirectory(prefix="w1-phase1-") as raw:
        raw_root = Path(raw)
        rows = [
            run_one(method, scenario, repeat, raw_root)
            for method in methods for scenario in scenarios for repeat in range(args.repeats)
        ]
    payload = {
        "benchmark": "w1-adaptive-evidence-fixture",
        "mode": "deterministic-semantic-fixture",
        "note": "Validates orchestration equivalence and fixture-mode overhead; it does not measure comparative LLM quality.",
        "raw": rows,
        "aggregate": aggregate(rows),
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0 if all(row.get("task_success") for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
