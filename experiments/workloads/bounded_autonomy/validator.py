"""Program-owned acceptance gate and oracle scoring for the perturbation suite.

The gate and the scoring are deliberately separate:

* ``validate_result`` is the *gate*. It is executed by the application inside the
  workflow and its ``problems`` list is fed back to the Agent on retry. It therefore
  must never contain oracle-derived information: no expected decision and no expected
  supporting source ids. Leaking those would let the Agent read the answer out of the
  retry feedback and would invalidate every autonomy and reliability measurement.
* ``score_result`` is the *scoring*. It compares the result against the scenario oracle
  and is executed only by the experiment harness, never inside the workflow.
"""

from __future__ import annotations

from experiments.workloads.bounded_autonomy.environment import load_scenario


DECISIONS = ("approve", "reject", "insufficient")


def gate_problems_from_scenario(scenario: dict, result: dict) -> tuple[list[str], list[str]]:
    """Return (problems, valid distinct cited source ids) using only public facts."""
    sources = {item["id"]: item for item in scenario["sources"]}
    requirements = scenario["requirements"]
    problems: list[str] = []

    decision = result.get("decision")
    if decision not in DECISIONS:
        problems.append(f"decision must be one of {list(DECISIONS)}")

    cited = result.get("cited_source_ids")
    if not isinstance(cited, list):
        cited = []
        problems.append("cited_source_ids must be a list")

    distinct: list[str] = []
    for source_id in cited:
        source = sources.get(source_id)
        if source is None:
            problems.append(f"unknown source: {source_id}")
            continue
        if not source["available"]:
            problems.append(f"unavailable source cited: {source_id}")
            continue
        if source_id not in distinct:
            distinct.append(source_id)

    # A result that claims a decision must carry enough of the required evidence.
    if decision != "insufficient":
        if len(distinct) < int(requirements["minimum_sources"]):
            problems.append("not enough valid evidence sources")

        kinds = {sources[source_id]["kind"] for source_id in distinct}
        missing_kinds = sorted(set(requirements["required_kinds"]) - kinds)
        if missing_kinds:
            problems.append(f"missing required evidence kinds: {missing_kinds}")

        if requirements.get("require_authoritative"):
            if not any(sources[source_id]["authoritative"] for source_id in distinct):
                problems.append("no authoritative evidence cited")

    return problems, distinct


def validate_result(scenario_id: str, result: dict) -> dict:
    """Feedback-safe acceptance gate executed by the application."""
    scenario = load_scenario(scenario_id)
    problems, distinct = gate_problems_from_scenario(scenario, result)
    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "valid_cited_source_ids": distinct,
    }


def score_result(scenario_id: str, result: dict) -> dict:
    """Oracle-based scoring executed by the harness only."""
    scenario = load_scenario(scenario_id)
    oracle = scenario["oracle"]
    problems, distinct = gate_problems_from_scenario(scenario, result)
    cited = set(result.get("cited_source_ids") or [])

    decision_correct = result.get("decision") == oracle["decision"]
    required = set(oracle.get("supporting_source_ids") or [])
    evidence_covered = required.issubset(cited)
    gate_ready = not problems

    return {
        "gate_ready": gate_ready,
        "gate_problems": problems,
        "decision_correct": decision_correct,
        "evidence_covered": evidence_covered,
        "expected_decision": oracle["decision"],
        "expected_supporting_source_ids": sorted(required),
        "task_success": bool(gate_ready and decision_correct and evidence_covered),
    }