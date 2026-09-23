"""LangGraph StateGraph on the controlled perturbation suite.

Each reachable action is an explicit node. A tool request that has no node bound to it
lands on `unavailable`, which reports the gap back to the model — a graph cannot grow a
route at runtime.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from experiments.workloads.bounded_autonomy.controlled.policy import AdaptiveDriverPolicy
from experiments.workloads.bounded_autonomy.controlled.protocol import (
    ACTION_LIST,
    ACTION_READ,
    MAX_ACTIONS_PER_ROUND,
    MAX_ROUNDS,
    STATUS_BUDGET,
    STATUS_COMPLETE,
    STATUS_INSUFFICIENT,
    ActionBudgetExceeded,
    RouteMissing,
    ToolSession,
    build_report,
    declared_actions_for,
    default_parser,
    write_report,
)
from experiments.workloads.bounded_autonomy.environment import load_scenario, public_scenario
from experiments.workloads.bounded_autonomy.validator import validate_result


IMPLEMENTATION = "langgraph"
# Declared development route: exactly one node is bound to each reachable action.
DECLARED_ACTIONS = (ACTION_READ,)


class State(TypedDict, total=False):
    scenario_id: str
    output: str
    routes_mode: str
    max_rounds: int
    public: dict[str, Any]
    allowed: tuple[str, ...]
    problems: list[str] | None
    round_index: int
    policy: AdaptiveDriverPolicy
    session: ToolSession
    request: dict[str, Any]
    result: dict[str, Any] | None
    validation: dict[str, Any] | None
    route_gaps: list[dict[str, Any]]
    tool_path: list[str]
    actions_used: int
    done: bool
    budget_exceeded: bool
    report: dict[str, Any]


def prepare(state: State) -> State:
    allowed = DECLARED_ACTIONS
    if state["routes_mode"] == "widened":
        from experiments.workloads.bounded_autonomy.controlled.langgraph.widened import (
            WIDENED_ACTIONS,
        )

        allowed = declared_actions_for(state["routes_mode"], DECLARED_ACTIONS, WIDENED_ACTIONS)
    scenario = load_scenario(state["scenario_id"])
    return {
        "public": public_scenario(scenario),
        "allowed": allowed,
        "problems": None,
        "round_index": 0,
        "route_gaps": [],
        "tool_path": [],
        "actions_used": 0,
        "done": False,
        "budget_exceeded": False,
    }


def start_round(state: State) -> State:
    previous = state.get("session")
    tool_path = list(state.get("tool_path", []))
    actions_used = int(state.get("actions_used", 0))
    if previous is not None:
        tool_path.extend(previous.tool_path)
        actions_used += len(previous.observations)

    policy = AdaptiveDriverPolicy(state["public"])
    policy.note_feedback(state.get("problems"))
    session = ToolSession(state["scenario_id"], tuple(state["allowed"]), max_actions=MAX_ACTIONS_PER_ROUND)
    return {
        "policy": policy,
        "session": session,
        "round_index": state["round_index"] + 1,
        "done": False,
        "tool_path": tool_path,
        "actions_used": actions_used,
    }


def plan(state: State) -> State:
    request = state["policy"].next_request(state["session"])
    if request["kind"] == "finish":
        return {"request": request, "result": request["result"], "done": True}
    return {"request": request}


def route_plan(state: State) -> str:
    if state.get("budget_exceeded"):
        return "finalize"
    if state["done"]:
        return "gate"
    return "read" if state["request"]["kind"] == ACTION_READ else "list"


def execute_read(state: State) -> State:
    return _execute(state)


def execute_list(state: State) -> State:
    return _execute(state)


def _execute(state: State) -> State:
    session = state["session"]
    try:
        session.execute(state["request"])
    except RouteMissing as exc:
        session.record_unsupported(state["request"], exc)
        state["policy"].observe_unsupported(exc.action)
        return {"route_gaps": [*state["route_gaps"], exc.as_dict()]}
    except ActionBudgetExceeded:
        return {"budget_exceeded": True}
    return {}


def unavailable(state: State) -> State:
    """No node is bound to the requested action: report the gap and keep going."""
    request = state["request"]
    error = RouteMissing(str(request["kind"]), tuple(state["allowed"]), state["session"].stage)
    state["session"].record_unsupported(request, error)
    state["policy"].observe_unsupported(error.action)
    return {"route_gaps": [*state["route_gaps"], error.as_dict()]}


def gate(state: State) -> State:
    return {"validation": validate_result(state["scenario_id"], state["result"])}


def route_gate(state: State) -> str:
    if state["validation"]["status"] == "ready":
        return "finalize"
    if state["round_index"] < state["max_rounds"]:
        return "start_round"
    return "finalize"


def finalize(state: State) -> State:
    validation = state.get("validation")
    status = STATUS_COMPLETE if validation and validation["status"] == "ready" else STATUS_INSUFFICIENT
    if state.get("budget_exceeded"):
        status = STATUS_BUDGET
    session = state["session"]
    report = build_report(
        scenario_id=state["scenario_id"], implementation=IMPLEMENTATION,
        routes_mode=state["routes_mode"], status=status, session=session,
        result=state.get("result"), validation=validation, rounds=state["round_index"],
        route_gaps=state.get("route_gaps"),
        error="action budget exceeded" if state.get("budget_exceeded") else None,
    )
    report["tool_path"] = [*state.get("tool_path", []), *session.tool_path]
    report["actions_used"] = int(state.get("actions_used", 0)) + len(session.observations)
    write_report(state["output"], report)
    return {"report": report}


def path_map(routes_mode: str) -> dict[str, str]:
    if routes_mode == "widened":
        from experiments.workloads.bounded_autonomy.controlled.langgraph.widened import (
            widened_path_map,
        )

        return widened_path_map()
    return {"read": "read_source", "list": "unavailable", "gate": "gate", "finalize": "finalize"}


def build_graph(routes_mode: str, max_rounds: int):
    graph = StateGraph(State)
    for name, fn in [
        ("prepare", prepare), ("start_round", start_round), ("plan", plan),
        ("read_source", execute_read), ("unavailable", unavailable),
        ("gate", gate), ("finalize", finalize),
    ]:
        graph.add_node(name, fn)
    if routes_mode == "widened":
        graph.add_node("discover", execute_list)
        graph.add_edge("discover", "plan")

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "start_round")
    graph.add_edge("start_round", "plan")
    graph.add_conditional_edges("plan", route_plan, path_map(routes_mode))
    graph.add_edge("read_source", "plan")
    graph.add_edge("unavailable", "plan")
    graph.add_conditional_edges("gate", route_gate, {"start_round": "start_round", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    return graph.compile()


def run(scenario_id: str, output: str, routes_mode: str = "dev", max_rounds: int = MAX_ROUNDS) -> dict:
    return build_graph(routes_mode, max_rounds).invoke(
        {
            "scenario_id": scenario_id,
            "output": output,
            "routes_mode": routes_mode,
            "max_rounds": max_rounds,
        }
    )["report"]


def main() -> int:
    parser = default_parser(IMPLEMENTATION)
    args = parser.parse_args()
    report = run(args.scenario, args.output, args.routes, args.max_rounds)
    print(f"RQ2_RESULT implementation={IMPLEMENTATION} status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())