from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = HERE / "scenarios.json"


def load_all_scenarios(path: str | Path = DEFAULT_SCENARIOS) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_scenario(scenario_id: str, path: str | Path = DEFAULT_SCENARIOS) -> dict[str, Any]:
    for scenario in load_all_scenarios(path):
        if scenario["id"] == scenario_id:
            return scenario
    raise KeyError(f"unknown scenario: {scenario_id}")


def public_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in scenario.items() if key not in {"oracle", "fixture"}}


def source_map(scenario: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in scenario["sources"]}


def validate_evidence(public: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    sources = source_map(public)
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        return {"status": "revise", "problems": ["evidence must be a list"]}

    valid_ids: list[str] = []
    authoritative = False
    for item in evidence:
        if not isinstance(item, dict):
            problems.append("each evidence item must be an object")
            continue
        source_id = item.get("source_id")
        claim = item.get("claim")
        if source_id not in sources:
            problems.append(f"unknown source_id: {source_id}")
            continue
        source = sources[source_id]
        if not source.get("available", False):
            problems.append(f"source is unavailable: {source_id}")
            continue
        if not isinstance(claim, str) or not claim.strip():
            problems.append(f"empty claim for source: {source_id}")
            continue
        valid_ids.append(source_id)
        authoritative = authoritative or bool(source.get("authoritative"))

    minimum = int(public["requirements"].get("minimum_evidence", 1))
    if len(set(valid_ids)) < minimum:
        problems.append(f"need at least {minimum} distinct available evidence sources; got {len(set(valid_ids))}")
    if public["requirements"].get("require_authoritative_source") and not authoritative:
        problems.append("at least one authoritative source is required")

    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "valid_source_ids": sorted(set(valid_ids)),
    }


def validate_analysis(public: dict[str, Any], evidence: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    allowed_ids = {
        item.get("source_id")
        for item in evidence.get("evidence", [])
        if isinstance(item, dict)
    }
    cited = analysis.get("cited_source_ids")
    if not isinstance(cited, list) or not cited:
        problems.append("analysis must cite at least one evidence source")
        cited = []
    unknown = sorted({item for item in cited if item not in allowed_ids})
    if unknown:
        problems.append(f"analysis cites sources not present in accepted evidence: {unknown}")
    if analysis.get("decision") not in {"approve", "reject", "insufficient"}:
        problems.append("analysis decision is invalid")
    if not isinstance(analysis.get("rationale"), str) or not analysis["rationale"].strip():
        problems.append("analysis rationale is empty")
    if analysis.get("needs_revision") is True:
        problems.append("analysis explicitly requests revision")
    return {"status": "ready" if not problems else "revise", "problems": problems}


def build_report(scenario_id: str, evidence: dict[str, Any] | None, analysis: dict[str, Any] | None, *, status: str, research_rounds: int, analysis_rounds: int, implementation: str) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "implementation": implementation,
        "status": status,
        "research_rounds": research_rounds,
        "analysis_rounds": analysis_rounds,
        "evidence": evidence or {},
        "analysis": analysis or {},
    }


def evaluate_report(scenario: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    oracle = scenario["oracle"]
    analysis = report.get("analysis") or {}
    decision_correct = analysis.get("decision") == oracle["expected_decision"]
    cited = set(analysis.get("cited_source_ids") or [])
    required = set(oracle.get("supporting_source_ids") or [])
    evidence_recall = 1.0 if not required else len(cited & required) / len(required)
    complete_expected = oracle["expected_decision"] != "insufficient"
    status_ok = report.get("status") == "complete" if complete_expected else report.get("status") in {"complete", "insufficient_evidence"}
    return {
        "decision_correct": decision_correct,
        "evidence_recall": round(evidence_recall, 4),
        "status_ok": status_ok,
        "task_success": bool(decision_correct and status_ok and evidence_recall == 1.0),
    }


def write_report(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(target), "bytes": target.stat().st_size}
