"""Microsoft Agent Framework functional workflow on the controlled suite."""

from __future__ import annotations

import argparse
import asyncio
import time

from agent_framework import workflow

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
    write_report,
)
from experiments.workloads.bounded_autonomy.environment import load_scenario, public_scenario
from experiments.workloads.bounded_autonomy.validator import validate_result


IMPLEMENTATION = "microsoft_agent_framework"
# Declared development route: read the candidate sources, evaluate, decide.
DECLARED_ACTIONS = (ACTION_READ,)


@workflow
async def controlled_scenario(payload: dict) -> dict:
    scenario_id = payload["scenario_id"]
    output = payload["output"]
    routes_mode = payload["routes_mode"]
    max_rounds = int(payload["max_rounds"])

    allowed = DECLARED_ACTIONS
    if routes_mode == "widened":
        from experiments.workloads.bounded_autonomy.controlled.microsoft_agent_framework.widened import (
            WIDENED_ACTIONS,
        )

        allowed = declared_actions_for(routes_mode, DECLARED_ACTIONS, WIDENED_ACTIONS)

    scenario = load_scenario(scenario_id)
    public = public_scenario(scenario)
    problems = None
    result = None
    validation = None
    rounds = 0
    route_gaps: list[dict] = []
    tool_path: list[str] = []
    actions_used = 0
    budget_exceeded = False

    for _ in range(max_rounds):
        rounds += 1
        policy = AdaptiveDriverPolicy(public)
        policy.note_feedback(problems)
        session = ToolSession(scenario_id, allowed, max_actions=MAX_ACTIONS_PER_ROUND)
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
            except ActionBudgetExceeded:
                budget_exceeded = True
                break

        actions_used += len(session.observations)
        tool_path.extend(session.tool_path)
        if budget_exceeded:
            break
        validation = validate_result(scenario_id, result)
        if validation["status"] == "ready":
            break
        problems = validation["problems"]

    status = STATUS_COMPLETE if validation and validation["status"] == "ready" else STATUS_INSUFFICIENT
    if budget_exceeded:
        status = STATUS_BUDGET
    report = build_report(
        scenario_id=scenario_id, implementation=IMPLEMENTATION, routes_mode=routes_mode,
        status=status, session=session, result=result, validation=validation, rounds=rounds,
        route_gaps=route_gaps,
        error="action budget exceeded" if budget_exceeded else None,
    )
    report["tool_path"] = tool_path
    report["actions_used"] = actions_used
    write_report(output, report)
    return report


async def run(args) -> dict:
    instance = controlled_scenario.build()
    result = await instance.run(
        {
            "scenario_id": args.scenario,
            "output": args.output,
            "routes_mode": args.routes,
            "max_rounds": args.max_rounds,
        }
    )
    outputs = result.get_outputs()
    if not outputs:
        raise RuntimeError("Microsoft Agent Framework workflow produced no output")
    return outputs[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--routes", choices=["dev", "widened"], default="dev")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()
    started = time.perf_counter()
    report = asyncio.run(run(args))
    print(f"RQ2_RESULT implementation={IMPLEMENTATION} status={report['status']} elapsed_ms={(time.perf_counter() - started) * 1000:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())