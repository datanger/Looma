"""Direct SDK / hand-written loop on the controlled perturbation suite.

The application declares the actions its hand-written pipeline can perform. Development
rounds iterate the pipeline against the development split; the route set is then frozen.
"""

from __future__ import annotations

from experiments.workloads.bounded_autonomy.controlled.policy import AdaptiveDriverPolicy
from experiments.workloads.bounded_autonomy.controlled.protocol import (
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


IMPLEMENTATION = "direct_sdk"
# Declared development route: read the candidate sources, evaluate, decide.
DECLARED_ACTIONS = (ACTION_READ,)


def run(scenario_id: str, output: str, routes_mode: str = "dev", max_rounds: int = MAX_ROUNDS) -> dict:
    scenario = load_scenario(scenario_id)
    public = public_scenario(scenario)
    if routes_mode == "widened":
        from experiments.workloads.bounded_autonomy.controlled.direct_sdk.widened import (
            WIDENED_ACTIONS,
        )

        allowed = declared_actions_for(routes_mode, DECLARED_ACTIONS, WIDENED_ACTIONS)
    else:
        allowed = DECLARED_ACTIONS

    problems: list[str] | None = None
    result = None
    validation = None
    rounds = 0
    total_actions = 0
    tool_path: list[str] = []
    route_gaps: list[dict] = []

    for _ in range(max_rounds):
        rounds += 1
        policy = AdaptiveDriverPolicy(public)
        policy.note_feedback(problems)
        session = ToolSession(scenario_id, allowed, max_actions=MAX_ACTIONS_PER_ROUND)
        try:
            while True:
                request = policy.next_request(session)
                if request["kind"] == "finish":
                    result = request["result"]
                    break
                try:
                    session.execute(request)
                except RouteMissing as exc:
                    route_gaps.append(exc.as_dict())
                    session.record_unsupported(request, exc)
                    policy.observe_unsupported(exc.action)
        except ActionBudgetExceeded as exc:
            report = build_report(
                scenario_id=scenario_id, implementation=IMPLEMENTATION, routes_mode=routes_mode,
                status=STATUS_BUDGET, session=session, rounds=rounds,
                error=f"action budget exceeded: {exc.used} > {exc.limit}",
            )
            write_report(output, report)
            return report

        total_actions += len(session.observations)
        tool_path.extend(session.tool_path)
        validation = validate_result(scenario_id, result)
        if validation["status"] == "ready":
            break
        problems = validation["problems"]

    status = STATUS_COMPLETE if validation and validation["status"] == "ready" else STATUS_INSUFFICIENT
    report = build_report(
        scenario_id=scenario_id, implementation=IMPLEMENTATION, routes_mode=routes_mode,
        status=status, session=session, result=result, validation=validation, rounds=rounds,
        route_gaps=route_gaps,
    )
    report["actions_used"] = total_actions
    report["tool_path"] = tool_path
    write_report(output, report)
    return report


def main() -> int:
    parser = default_parser(IMPLEMENTATION)
    args = parser.parse_args()
    report = run(args.scenario, args.output, args.routes, args.max_rounds)
    print(f"RQ2_RESULT implementation={IMPLEMENTATION} status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())