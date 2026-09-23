"""Direct SDK / hand-written retrieval loop on the public perturbation suite.

The application owns the retrieval trajectory *and* the set of actions that
trajectory can reach. Development rounds iterate the pipeline against the
development split; the route set is then frozen, and the evaluation split is the
first time the author discovers what else the environment can ask for.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.workloads.retrieval_perturbation.driver import AdaptiveRetrievalDriver
from experiments.workloads.retrieval_perturbation.injectors import (
    DEV_ROUTE_SET,
    Environment,
    split_of,
)
from experiments.workloads.retrieval_perturbation.protocol import (
    MAX_ACTIONS_PER_ROUND,
    MAX_ROUNDS,
    STATUS_BUDGET,
    STATUS_COMPLETE,
    STATUS_DEAD_END,
    STATUS_ERROR,
    STATUS_INSUFFICIENT,
    ActionBudgetExceeded,
    RetrievalSession,
    RouteMissing,
    build_report,
    validate_result,
    write_report,
    write_session,
)

IMPLEMENTATION = "direct_sdk"

#: Frozen after the development split: the obvious semantic/keyword fallback is
#: already covered. Nothing here can enumerate a corpus whose identifiers moved.
DECLARED_ACTIONS = DEV_ROUTE_SET


def routes_for(routes_mode: str) -> tuple[str, ...]:
    if routes_mode == "dev":
        return DECLARED_ACTIONS
    if routes_mode == "widened":
        from experiments.workloads.retrieval_perturbation.direct_sdk.widened import (
            WIDENED_ACTIONS,
        )

        return WIDENED_ACTIONS
    raise ValueError(f"unknown routes mode: {routes_mode!r}")


def run(instance_file: str, output: str, session_file: str, routes_mode: str = "dev") -> dict:
    environment = Environment.from_payload(
        json.loads(Path(instance_file).read_text(encoding="utf-8"))
    )
    instance_id = f"{environment.dataset}:{environment.qid}:{environment.perturbation}"
    session = RetrievalSession(
        environment,
        routes_for(routes_mode),
        max_actions=MAX_ACTIONS_PER_ROUND,
    )

    result = None
    status = STATUS_DEAD_END
    error = None
    rounds = 0
    driver = AdaptiveRetrievalDriver(environment.question)

    for _ in range(MAX_ROUNDS):
        rounds += 1
        try:
            while True:
                request = driver.next_action(session)
                if request is None:
                    break
                try:
                    session.execute(request)
                except RouteMissing as missing:
                    session.record_unsupported(missing)
        except ActionBudgetExceeded as exceeded:
            status = STATUS_BUDGET
            error = f"action budget exceeded: {exceeded.used} > {exceeded.limit}"
            break

        try:
            result = driver.finish(session)
        except Exception as exc:  # pragma: no cover - defensive
            status = STATUS_ERROR
            error = f"{type(exc).__name__}: {exc}"
            break
        status = STATUS_COMPLETE if result["status"] == "answered" else STATUS_INSUFFICIENT
        break

    write_session(session_file, session.as_dict(status))
    validation = validate_result(result, session_file) if result is not None else None
    report = build_report(
        instance_id=instance_id,
        implementation=IMPLEMENTATION,
        routes_mode=routes_mode,
        status=status,
        session=session,
        result=result,
        validation=validation,
        rounds=rounds,
        error=error,
    )
    report["split"] = split_of(environment.perturbation)
    write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=f"retrieval perturbation: {IMPLEMENTATION}")
    parser.add_argument("--instance", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--routes", choices=["dev", "widened"], default="dev")
    args = parser.parse_args()
    report = run(args.instance, args.output, args.session, args.routes)
    print(
        f"RETRIEVAL_RESULT implementation={IMPLEMENTATION} "
        f"routes={args.routes} status={report['status']} "
        f"gaps={len(report['route_gaps'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())