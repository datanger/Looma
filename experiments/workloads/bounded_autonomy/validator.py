from __future__ import annotations

from experiments.workloads.bounded_autonomy.environment import load_scenario


def validate_result(scenario_id: str, result: dict) -> dict:
    scenario = load_scenario(scenario_id)
    sources = {item["id"]: item for item in scenario["sources"]}
    requirements = scenario["requirements"]
    problems: list[str] = []

    cited = result.get("cited_source_ids")
    if not isinstance(cited, list):
        cited = []
        problems.append("cited_source_ids must be a list")

    distinct = []
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

    if len(distinct) < int(requirements["minimum_sources"]):
        if scenario["oracle"]["decision"] != "insufficient":
            problems.append("not enough valid evidence sources")

    kinds = {sources[source_id]["kind"] for source_id in distinct}
    missing_kinds = sorted(set(requirements["required_kinds"]) - kinds)
    if missing_kinds and result.get("decision") != "insufficient":
        problems.append(f"missing required evidence kinds: {missing_kinds}")

    if requirements.get("require_authoritative"):
        if not any(sources[source_id]["authoritative"] for source_id in distinct):
            problems.append("no authoritative evidence cited")

    if result.get("decision") != scenario["oracle"]["decision"]:
        problems.append(
            f"decision mismatch: expected {scenario['oracle']['decision']}"
        )

    required = set(scenario["oracle"]["supporting_source_ids"])
    if not required.issubset(set(distinct)):
        problems.append(
            "oracle supporting evidence not fully covered: "
            + ", ".join(sorted(required - set(distinct)))
        )

    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "valid_cited_source_ids": distinct,
    }
