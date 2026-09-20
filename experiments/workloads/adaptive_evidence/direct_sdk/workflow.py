from __future__ import annotations

import argparse
import time

from experiments.workloads.adaptive_evidence.shared.backend import FixtureSemanticBackend
from experiments.workloads.adaptive_evidence.shared.workload import (
    build_report, load_scenario, public_scenario, validate_analysis,
    validate_evidence, write_report,
)


def run(scenario_id: str, output: str, max_rounds: int = 3) -> dict:
    scenario = load_scenario(scenario_id)
    public = public_scenario(scenario)
    backend = FixtureSemanticBackend(scenario_id)

    evidence = None
    evidence_check = {"status": "revise", "problems": ["not started"]}
    research_rounds = 0
    for round_index in range(max_rounds):
        research_rounds += 1
        evidence = backend.research({
            "phase": "research", "round": round_index, "scenario": public,
            "problems": evidence_check["problems"],
        })
        evidence_check = validate_evidence(public, evidence)
        if evidence_check["status"] == "ready":
            break

    analysis = None
    analysis_check = {"status": "revise", "problems": ["not started"]}
    analysis_rounds = 0
    if evidence_check["status"] == "ready" and evidence is not None:
        for round_index in range(max_rounds):
            analysis_rounds += 1
            analysis = backend.analyze({
                "phase": "analysis", "round": round_index, "scenario": public,
                "evidence": evidence, "problems": analysis_check["problems"],
            })
            analysis_check = validate_analysis(public, evidence, analysis)
            if analysis_check["status"] == "ready":
                break

    status = "complete" if evidence_check["status"] == "ready" and analysis_check["status"] == "ready" else "insufficient_evidence"
    report = build_report(
        scenario_id, evidence, analysis, status=status,
        research_rounds=research_rounds, analysis_rounds=analysis_rounds,
        implementation="direct_sdk",
    )
    write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    started = time.perf_counter()
    report = run(args.scenario, args.output, args.max_rounds)
    print(f"W1_RESULT status={report['status']} elapsed_ms={(time.perf_counter() - started) * 1000:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
