from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.workloads.bounded_autonomy.environment import (
    list_sources,
    load_scenarios,
    read_source,
)
from experiments.workloads.bounded_autonomy.validator import validate_result
from experiments.workloads.bounded_autonomy.validator import score_result


def feedback_leaks_oracle(scenario: dict, problems: list[str]) -> bool:
    """True if retry feedback would hand the Agent oracle-only information."""
    joined = " ".join(problems)
    needles = [str(scenario["oracle"]["decision"])]
    needles.extend(str(item) for item in scenario["oracle"].get("supporting_source_ids") or [])
    for needle in needles:
        # The decision word may legitimately appear as part of the enum list.
        if needle in {"approve", "reject", "insufficient"} and f"expected {needle}" not in joined:
            continue
        if needle and needle in joined:
            return True
    return False


def static_route(scenario: dict) -> dict:
    inspected = []
    for source_id in scenario["static_route"]:
        observation = read_source(scenario["id"], source_id)
        inspected.append(observation)

    valid = [
        item["source_id"]
        for item in inspected
        if item.get("status") == "ready"
    ]
    return {
        "decision": (
            scenario["oracle"]["decision"]
            if set(scenario["oracle"]["supporting_source_ids"]).issubset(set(valid))
            else "insufficient"
        ),
        "cited_source_ids": valid,
        "tool_path": [f"read:{item}" for item in scenario["static_route"]],
        "rationale": "predefined static route",
    }


def adaptive_oracle(scenario: dict) -> dict:
    catalog = list_sources(scenario["id"])["sources"]
    inspected = []
    authoritative = [
        item for item in catalog
        if item["available"] and item["authoritative"]
    ]
    others = [
        item for item in catalog
        if item["available"] and not item["authoritative"]
    ]
    for item in [*authoritative, *others]:
        inspected.append(read_source(scenario["id"], item["id"]))

    required = set(scenario["oracle"]["supporting_source_ids"])
    cited = [
        item["source_id"]
        for item in inspected
        if item.get("status") == "ready"
        and item["source_id"] in required
    ]
    return {
        "decision": scenario["oracle"]["decision"],
        "cited_source_ids": cited,
        "tool_path": [
            "list_sources",
            *[f"read:{item['source_id']}" for item in inspected],
        ],
        "rationale": "adaptive oracle used only to validate benchmark discriminative behavior",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = []
    for scenario in load_scenarios():
        static = static_route(scenario)
        adaptive = adaptive_oracle(scenario)
        static_check = validate_result(scenario["id"], static)
        adaptive_check = validate_result(scenario["id"], adaptive)
        static_score = score_result(scenario["id"], static)
        adaptive_score = score_result(scenario["id"], adaptive)
        rows.append(
            {
                "scenario_id": scenario["id"],
                "static_success": static_score["task_success"],
                "adaptive_oracle_success": adaptive_score["task_success"],
                "static_tool_path": static["tool_path"],
                "adaptive_tool_path": adaptive["tool_path"],
                "static_problems": static_check["problems"],
                "adaptive_problems": adaptive_check["problems"],
                "gate_feedback_problems": static_check["problems"],
                "gate_feedback_leaks_oracle": feedback_leaks_oracle(
                    scenario, static_check["problems"]
                ),
            }
        )

    payload = {
        "benchmark": "bounded-autonomy-perturbation-sanity",
        "note": (
            "The adaptive oracle is not an Agent baseline. This run only verifies "
            "that the perturbation suite distinguishes a fixed predefined path "
            "from a path that can adapt. Real Host Agents must be evaluated separately."
        ),
        "scenarios": rows,
        "summary": {
            "scenarios": len(rows),
            "static_success_rate": round(
                sum(row["static_success"] for row in rows) / len(rows), 4
            ),
            "adaptive_oracle_success_rate": round(
                sum(row["adaptive_oracle_success"] for row in rows) / len(rows), 4
            ),
            "gate_feedback_leaks_oracle": any(
                row["gate_feedback_leaks_oracle"] for row in rows
            ),
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
