from __future__ import annotations

import argparse

from looma import agent, step, workflow

from experiments.workloads.bounded_autonomy.environment import (
    load_scenario,
    public_scenario,
)
from experiments.workloads.bounded_autonomy.validator import validate_result


AGENT_INPUT_SCHEMA = {
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
        "previous_validation_problems": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": False,
}


RESULT_SCHEMA = {
    "type": "object",
    "required": ["decision", "cited_source_ids", "tool_path", "rationale"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["approve", "reject", "insufficient"],
        },
        "cited_source_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tool_path": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rationale": {"type": "string"},
    },
    "additionalProperties": False,
}


@workflow
def run_scenario(scenario_id: str, max_rounds: int = 3):
    scenario = step(load_scenario, scenario_id)
    public = public_scenario(scenario)
    check = {"status": "revise", "problems": ["not started"]}
    result = None

    for round_index in range(max_rounds):
        result = agent(
            task=(
                "Resolve the bounded-autonomy scenario. Use the current Host's "
                "terminal/tool capability to invoke "
                "experiments.workloads.bounded_autonomy.environment. "
                "You may list and read sources in any order. Adapt when a source "
                "is missing, unavailable, renamed, or conflicts with other evidence. "
                "Prefer authoritative current evidence. Do not launch another Agent. "
                "Return only a decision supported by sources you actually inspected."
            ),
            input={
                "scenario": public,
                "scenario_id": scenario_id,
                "round": round_index,
                "environment_module": (
                    "experiments.workloads.bounded_autonomy.environment"
                ),
                "previous_validation_problems": check["problems"],
            },
            input_schema=AGENT_INPUT_SCHEMA,
            output_schema=RESULT_SCHEMA,
        )
        check = step(validate_result, scenario_id, result)
        if check["status"] == "ready":
            break

    return {
        "status": (
            "complete"
            if check["status"] == "ready"
            else "insufficient_evidence"
        ),
        "result": result,
        "validation": check,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    run_scenario(args.scenario, args.max_rounds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
