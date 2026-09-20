from __future__ import annotations

import argparse

from looma import agent, step, workflow

from experiments.workloads.adaptive_evidence.shared.contracts import ANALYSIS_SCHEMA, EVIDENCE_SCHEMA
from experiments.workloads.adaptive_evidence.shared.workload import (
    build_report, load_scenario, public_scenario, validate_analysis,
    validate_evidence, write_report,
)


@workflow
def run_workflow(scenario_id: str, output: str, max_rounds: int = 3) -> dict:
    scenario = step(load_scenario, scenario_id)
    public = public_scenario(scenario)

    evidence = None
    evidence_check = {"status": "revise", "problems": ["not started"]}
    research_rounds = 0
    for round_index in range(max_rounds):
        research_rounds += 1
        evidence = agent(
            task="W1 research boundary. Gather enough available evidence for the question. Adapt the internal search/tool path when an attempted source is unavailable.",
            input={"phase": "research", "round": round_index, "scenario": public, "problems": evidence_check["problems"]},
            output_schema=EVIDENCE_SCHEMA,
        )
        evidence_check = step(validate_evidence, public, evidence)
        if evidence_check["status"] == "ready":
            break

    analysis = None
    analysis_check = {"status": "revise", "problems": ["not started"]}
    analysis_rounds = 0
    if evidence_check["status"] == "ready" and evidence is not None:
        for round_index in range(max_rounds):
            analysis_rounds += 1
            analysis = agent(
                task="W1 analysis boundary. Decide approve, reject, or insufficient using only the accepted evidence. Cite the evidence used and revise if validation failed.",
                input={"phase": "analysis", "round": round_index, "scenario": public, "evidence": evidence, "problems": analysis_check["problems"]},
                output_schema=ANALYSIS_SCHEMA,
            )
            analysis_check = step(validate_analysis, public, evidence, analysis)
            if analysis_check["status"] == "ready":
                break

    status = "complete" if evidence_check["status"] == "ready" and analysis_check["status"] == "ready" else "insufficient_evidence"
    report = build_report(
        scenario_id, evidence, analysis, status=status,
        research_rounds=research_rounds, analysis_rounds=analysis_rounds,
        implementation="looma",
    )
    step(write_report, output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    run_workflow(args.scenario, args.output, args.max_rounds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
