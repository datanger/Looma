"""Regression tests for the controlled RQ2 perturbation comparison.

These tests pin the properties the paper's RQ2 table depends on:

* the development split is solvable with the route set an author would declare for it;
* the held-out split defeats that route set and is solvable once the route is widened;
* AEP/Looma reaches both splits with a byte-identical application file and no declared
  action route, because the Host owns the route set;
* a route gap is recorded as data, never as a silent success.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from experiments.workloads.bounded_autonomy.controlled.policy import AdaptiveDriverPolicy
from experiments.workloads.bounded_autonomy.controlled.protocol import (
    ACTION_LIST,
    ACTION_READ,
    RouteMissing,
    ToolSession,
)
from experiments.workloads.bounded_autonomy.controlled.run_controlled import run_one
from experiments.workloads.bounded_autonomy.environment import (
    load_scenario,
    load_scenarios,
    public_scenario,
    split_of,
)
from experiments.workloads.bounded_autonomy.validator import validate_result


DISCOVERY_SCENARIOS = (
    "renamed_authoritative_source",
    "missing_review_replaced_by_audit",
    "authoritative_only_after_discovery",
)


def _drive(scenario_id: str, allowed_actions: tuple[str, ...]) -> tuple[list[str], dict]:
    """Run the shared policy through a session with the given declared route set."""
    scenario = load_scenario(scenario_id)
    policy = AdaptiveDriverPolicy(public_scenario(scenario))
    session = ToolSession(scenario_id, allowed_actions)
    requested: list[str] = []
    while True:
        request = policy.next_request(session)
        requested.append(request["kind"])
        if request["kind"] == "finish":
            return requested, request["result"]
        try:
            session.execute(request)
        except RouteMissing as exc:
            session.record_unsupported(request, exc)
            policy.observe_unsupported(exc.action)


def test_development_split_is_solvable_without_discovery():
    for scenario in load_scenarios():
        if split_of(scenario) != "dev":
            continue
        requested, result = _drive(scenario["id"], (ACTION_READ,))
        assert ACTION_LIST not in requested, scenario["id"]
        assert validate_result(scenario["id"], result)["status"] == "ready", scenario["id"]


def test_held_out_split_requires_the_discovery_route():
    for scenario_id in DISCOVERY_SCENARIOS:
        requested, _ = _drive(scenario_id, (ACTION_READ,))
        assert ACTION_LIST in requested, scenario_id


def test_declared_route_is_defeated_on_the_held_out_split_and_widening_fixes_it():
    with tempfile.TemporaryDirectory(prefix="rq2-test-") as raw:
        raw_root = Path(raw)
        for scenario_id in DISCOVERY_SCENARIOS:
            scenario = load_scenario(scenario_id)
            frozen = run_one("direct_sdk", "dev", scenario, raw_root)
            widened = run_one("direct_sdk", "widened", scenario, raw_root)

            assert frozen["task_success"] is False, scenario_id
            assert frozen["declared_actions"] == [ACTION_READ]
            assert [gap["action"] for gap in frozen["route_gaps"]] == [ACTION_LIST]

            assert widened["task_success"] is True, scenario_id
            assert widened["route_gaps"] == []
            assert widened["route_declaration_delta_sloc"] > 0


def test_control_scenario_is_reachable_with_the_declared_route():
    """Not every held-out scenario must fail: the suite is not uniformly adversarial."""
    with tempfile.TemporaryDirectory(prefix="rq2-test-") as raw:
        scenario = load_scenario("insufficient_after_adaptation")
        assert split_of(scenario) == "eval"
        row = run_one("direct_sdk", "dev", scenario, Path(raw))
        assert row["task_success"] is True


def test_aep_route_set_is_host_owned_and_the_application_is_unchanged():
    with tempfile.TemporaryDirectory(prefix="rq2-test-") as raw:
        raw_root = Path(raw)
        dev_row = run_one("looma", "dev", load_scenario("normal"), raw_root)
        eval_row = run_one("looma", "widened", load_scenario("renamed_authoritative_source"), raw_root)

        assert dev_row["task_success"] is True
        assert eval_row["task_success"] is True
        # Same command, same file: the held-out split cost the application nothing.
        assert dev_row["application_sha256"] == eval_row["application_sha256"]
        assert dev_row["application_declared_actions"] == [], "the application must declare no tool route"
        assert dev_row["declared_actions"] == [ACTION_READ, ACTION_LIST], "the Host owns the route set"
        assert eval_row["route_gaps"] == []
        # The Host route is reported separately and is never counted as application code.
        assert dev_row["host_driver_sloc"] > 0
        assert dev_row["host_driver_file"] == "looma/host_driver.py"
        assert dev_row["application_sloc"] == dev_row["sloc"]


def test_looma_host_trace_records_the_discovery_path():
    with tempfile.TemporaryDirectory(prefix="rq2-test-") as raw:
        row = run_one("looma", "dev", load_scenario("missing_review_replaced_by_audit"), Path(raw))
        assert row["task_success"] is True
        assert ACTION_LIST in row["tool_path"]
        assert any(entry.startswith("read:audit-R35") for entry in row["tool_path"])