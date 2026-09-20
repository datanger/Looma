from __future__ import annotations

import argparse
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from experiments.workloads.adaptive_evidence.shared.backend import FixtureSemanticBackend
from experiments.workloads.adaptive_evidence.shared.workload import (
    build_report, load_scenario, public_scenario, validate_analysis,
    validate_evidence, write_report,
)


class State(TypedDict, total=False):
    scenario_id: str
    output: str
    max_rounds: int
    public: dict
    backend: FixtureSemanticBackend
    evidence: dict
    evidence_check: dict
    analysis: dict
    analysis_check: dict
    research_rounds: int
    analysis_rounds: int
    report: dict


def prepare(state: State) -> State:
    scenario = load_scenario(state["scenario_id"])
    return {
        "public": public_scenario(scenario),
        "backend": FixtureSemanticBackend(state["scenario_id"]),
        "evidence_check": {"status": "revise", "problems": ["not started"]},
        "analysis_check": {"status": "revise", "problems": ["not started"]},
        "research_rounds": 0,
        "analysis_rounds": 0,
    }


def research(state: State) -> State:
    round_index = state["research_rounds"]
    evidence = state["backend"].research({
        "phase": "research", "round": round_index, "scenario": state["public"],
        "problems": state["evidence_check"]["problems"],
    })
    return {"evidence": evidence, "research_rounds": round_index + 1}


def check_evidence(state: State) -> State:
    return {"evidence_check": validate_evidence(state["public"], state["evidence"])}


def route_evidence(state: State) -> str:
    if state["evidence_check"]["status"] == "ready":
        return "analysis"
    if state["research_rounds"] < state["max_rounds"]:
        return "research"
    return "finalize"


def analysis(state: State) -> State:
    round_index = state["analysis_rounds"]
    result = state["backend"].analyze({
        "phase": "analysis", "round": round_index, "scenario": state["public"],
        "evidence": state["evidence"], "problems": state["analysis_check"]["problems"],
    })
    return {"analysis": result, "analysis_rounds": round_index + 1}


def check_analysis(state: State) -> State:
    return {"analysis_check": validate_analysis(state["public"], state["evidence"], state["analysis"])}


def route_analysis(state: State) -> str:
    if state["analysis_check"]["status"] == "ready":
        return "finalize"
    if state["analysis_rounds"] < state["max_rounds"]:
        return "analysis"
    return "finalize"


def finalize(state: State) -> State:
    complete = state.get("evidence_check", {}).get("status") == "ready" and state.get("analysis_check", {}).get("status") == "ready"
    report = build_report(
        state["scenario_id"], state.get("evidence"), state.get("analysis"),
        status="complete" if complete else "insufficient_evidence",
        research_rounds=state.get("research_rounds", 0),
        analysis_rounds=state.get("analysis_rounds", 0),
        implementation="langgraph",
    )
    write_report(state["output"], report)
    return {"report": report}


def build_graph():
    graph = StateGraph(State)
    for name, fn in [
        ("prepare", prepare), ("research", research), ("check_evidence", check_evidence),
        ("analysis", analysis), ("check_analysis", check_analysis), ("finalize", finalize),
    ]:
        graph.add_node(name, fn)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "research")
    graph.add_edge("research", "check_evidence")
    graph.add_conditional_edges("check_evidence", route_evidence, {"research": "research", "analysis": "analysis", "finalize": "finalize"})
    graph.add_edge("analysis", "check_analysis")
    graph.add_conditional_edges("check_analysis", route_analysis, {"analysis": "analysis", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    return graph.compile()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    started = time.perf_counter()
    result = build_graph().invoke({"scenario_id": args.scenario, "output": args.output, "max_rounds": args.max_rounds})
    print(f"W1_RESULT status={result['report']['status']} elapsed_ms={(time.perf_counter() - started) * 1000:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
