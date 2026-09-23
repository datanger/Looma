"""AEP / Looma on the controlled perturbation suite.

The application declares no tool route at all: it declares a semantic task boundary
("obtain sufficient evidence ... and return a validated decision"), a Result Contract and
a program-owned acceptance gate. Which read/list actions the Host performs, and in which
order, is the Host's business — which is why this file is byte-identical for the
development and the held-out splits.
"""

from __future__ import annotations

from looma import agent, step, workflow

from experiments.workloads.bounded_autonomy.controlled.protocol import (
    MAX_ROUNDS,
    STATUS_COMPLETE,
    STATUS_INSUFFICIENT,
    build_report,
    write_report,
)
from experiments.workloads.bounded_autonomy.environment import load_scenario, public_scenario
from experiments.workloads.bounded_autonomy.validator import validate_result


IMPLEMENTATION = "looma"
ENVIRONMENT_MODULE = "experiments.workloads.bounded_autonomy.environment"

TASK = (
    "Resolve the controlled perturbation scenario using non-fabricated evidence.\n"
    "The environment is available through `environment_module` in the boundary input: you "
    "may inspect the catalog and read sources in any order, and you may revisit or reorder "
    "your evidence path freely when something is missing, unavailable, renamed, or "
    "conflicting.\n"
    "Requirements: prefer authoritative current sources over stale or non-authoritative "
    "ones; cite only sources you actually inspected; if the required evidence cannot be "
    "obtained, say so instead of guessing.\n"
    "Return only a decision supported by the sources you inspected. Do not launch another "
    "Agent or call a model API directly."
)

INPUT_SCHEMA = {
    "type": "object",
    "required": [
        "scenario",
        "scenario_id",
        "round",
        "environment_module",
        "previous_validation_problems",
    ],
    "properties": {
        "scenario": {"type": "object"},
        "scenario_id": {"type": "string"},
        "round": {"type": "integer"},
        "environment_module": {"type": "string"},
        "previous_validation_problems": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

RESULT_SCHEMA = {
    "type": "object",
    "required": ["decision", "cited_source_ids", "tool_path", "rationale"],
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "reject", "insufficient"]},
        "cited_source_ids": {"type": "array", "items": {"type": "string"}},
        "tool_path": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "additionalProperties": False,
}


@workflow
def resolve_scenario(scenario_id: str, output: str, max_rounds: int = MAX_ROUNDS) -> dict:
    scenario = step(load_scenario, scenario_id)
    public = step(public_scenario, scenario)

    check = {"status": "revise", "problems": ["not started"]}
    result = None
    rounds = 0
    for round_index in range(max_rounds):
        rounds += 1
        result = agent(
            task=TASK,
            input={
                "scenario": public,
                "scenario_id": scenario_id,
                "round": round_index,
                "environment_module": ENVIRONMENT_MODULE,
                "previous_validation_problems": check["problems"],
            },
            input_schema=INPUT_SCHEMA,
            output_schema=RESULT_SCHEMA,
        )
        check = step(validate_result, scenario_id, result)
        if check["status"] == "ready":
            break

    status = STATUS_COMPLETE if check["status"] == "ready" else STATUS_INSUFFICIENT
    report = build_report(
        scenario_id=scenario_id,
        implementation=IMPLEMENTATION,
        # The application declares no route; the Host owns the reachable action set.
        routes_mode="host_native",
        status=status,
        result=result,
        validation=check,
        rounds=rounds,
    )
    write_report(output, report)
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()
    report = resolve_scenario(args.scenario, args.output, args.max_rounds)
    print(f"RQ2_RESULT implementation={IMPLEMENTATION} status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())