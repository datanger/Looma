"""Shared tool surface and result plumbing for the controlled RQ2 comparison.

The single variable of the controlled comparison is *which actions the application's
orchestration can reach*. Every application talks to the environment through the same
`ToolSession`; a `ToolSession` is constructed with the action set the application
declares. When the deterministic driver policy (the fixture model) asks for an action the
application never declared a route for, the session raises `RouteMissing` and the run is
recorded as a dead end. That is the measured quantity, not a bug.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from experiments.workloads.bounded_autonomy.environment import (
    list_sources,
    load_scenario,
    public_scenario,
    read_source,
)

ACTION_READ = "read"
ACTION_LIST = "list"
ACTION_KINDS = (ACTION_READ, ACTION_LIST)
HOST_NATIVE_ACTIONS = (ACTION_READ, ACTION_LIST)
MAX_ACTIONS_PER_ROUND = 12
MAX_ROUNDS = 3

STATUS_COMPLETE = "complete"
STATUS_INSUFFICIENT = "insufficient_evidence"
STATUS_DEAD_END = "dead_end"
STATUS_BUDGET = "budget_exceeded"
STATUS_ERROR = "error"


class HarnessError(RuntimeError):
    pass


class RouteMissing(HarnessError):
    """The application declared no route for an action the policy asked for."""

    def __init__(self, action: str, allowed: tuple[str, ...], stage: str):
        super().__init__(
            f"no declared route for action {action!r} at stage {stage!r} "
            f"(declared actions: {', '.join(allowed) or 'none'})"
        )
        self.action = action
        self.allowed = list(allowed)
        self.stage = stage

    def as_dict(self) -> dict[str, Any]:
        return {"action": self.action, "declared_actions": self.allowed, "stage": self.stage}


class ActionBudgetExceeded(HarnessError):
    def __init__(self, used: int, limit: int):
        super().__init__(f"action budget exceeded: {used} > {limit}")
        self.used = used
        self.limit = limit


@dataclass
class ToolSession:
    scenario_id: str
    allowed_actions: tuple[str, ...] = HOST_NATIVE_ACTIONS
    max_actions: int = MAX_ACTIONS_PER_ROUND
    stage: str = "plan"
    observations: list[dict[str, Any]] = field(default_factory=list)
    tool_path: list[str] = field(default_factory=list)

    def record_unsupported(self, request: dict[str, Any], error: "RouteMissing") -> dict[str, Any]:
        """Report an undeclared action back to the policy instead of crashing the run.

        A workflow that cannot execute an action still owns the responsibility to make a
        decision from the evidence it can reach. The gap is recorded so the harness can
        attribute the outcome to the declared route set.
        """
        observation = {
            "kind": request.get("kind"),
            "source_id": request.get("source_id"),
            "result": {
                "status": "unsupported",
                "reason": "the application declared no route for this action",
                "action": error.action,
                "declared_actions": list(error.allowed),
            },
            "stage": error.stage,
        }
        self.observations.append(observation)
        self.tool_path.append(f"unsupported:{error.action}")
        return observation

    def execute(self, request: dict[str, Any], *, stage: str | None = None) -> dict[str, Any]:
        kind = request.get("kind")
        active_stage = stage or self.stage
        if kind not in ACTION_KINDS:
            raise HarnessError(f"unknown action kind: {kind!r}")
        if kind not in self.allowed_actions:
            raise RouteMissing(str(kind), tuple(self.allowed_actions), active_stage)
        if len(self.observations) >= self.max_actions:
            raise ActionBudgetExceeded(len(self.observations), self.max_actions)

        if kind == ACTION_LIST:
            result = list_sources(self.scenario_id)
            self.tool_path.append("list")
        else:
            source_id = str(request.get("source_id"))
            result = read_source(self.scenario_id, source_id)
            self.tool_path.append(f"read:{source_id}")

        observation = {
            "kind": kind,
            "source_id": request.get("source_id"),
            "result": result,
            "stage": active_stage,
        }
        self.observations.append(observation)
        return observation

    def read_sources(self) -> dict[str, dict[str, Any]]:
        """Successfully read source documents, keyed by source id."""
        documents: dict[str, dict[str, Any]] = {}
        for observation in self.observations:
            if observation["kind"] != ACTION_READ:
                continue
            result = observation["result"]
            if result.get("status") == "ready":
                documents[result["source_id"]] = result
        return documents

    def read_ids(self) -> set[str]:
        return {
            str(observation["source_id"])
            for observation in self.observations
            if observation["kind"] == ACTION_READ
        }

    def listed_sources(self) -> list[dict[str, Any]]:
        for observation in self.observations:
            if observation["kind"] != ACTION_LIST:
                continue
            result = observation["result"]
            if "sources" in result:
                return list(result["sources"])
        return []


def declared_actions_for(routes_mode: str, dev_actions: tuple[str, ...], widened_actions: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve the declared action set for a paradigm.

    `routes_mode="dev"` is the frozen route set the application author declared for the
    development split. `routes_mode="widened"` is the route set that the held-out split
    turns out to require; it is a separate declared configuration and is never edited in
    during a run.
    """
    if routes_mode == "dev":
        return dev_actions
    if routes_mode == "widened":
        return widened_actions
    raise HarnessError(f"unknown routes mode: {routes_mode!r}")


def build_report(
    *,
    scenario_id: str,
    implementation: str,
    routes_mode: str,
    status: str,
    session: ToolSession | None = None,
    result: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    rounds: int = 1,
    route_gaps: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    declared = list(session.allowed_actions) if session is not None else []
    tool_path = list(session.tool_path) if session is not None else []
    actions_used = len(session.observations) if session is not None else 0
    return {
        "scenario_id": scenario_id,
        "implementation": implementation,
        "routes_mode": routes_mode,
        "status": status,
        "rounds": rounds,
        "declared_actions": declared,
        "actions_used": actions_used,
        "tool_path": tool_path,
        "result": result,
        "validation": validation,
        "score": score,
        "route_gaps": route_gaps or [],
        "error": error,
    }


def write_report(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(target), "bytes": target.stat().st_size}


def default_parser(implementation: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"controlled RQ2 comparison: {implementation}")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--routes", choices=["dev", "widened"], default="dev")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    return parser


def load_public(scenario_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = load_scenario(scenario_id)
    return scenario, public_scenario(scenario)