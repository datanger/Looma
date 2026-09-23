from experiments.workloads.bounded_autonomy.environment import load_scenarios
from experiments.workloads.bounded_autonomy.sanity import (
    adaptive_oracle,
    feedback_leaks_oracle,
    static_route,
)
from experiments.workloads.bounded_autonomy.validator import score_result, validate_result


def test_bounded_autonomy_suite_has_real_perturbations():
    rows = []
    for scenario in load_scenarios():
        static_ok = score_result(scenario["id"], static_route(scenario))["task_success"]
        adaptive_ok = score_result(scenario["id"], adaptive_oracle(scenario))["task_success"]
        rows.append((scenario["id"], static_ok, adaptive_ok))

    assert all(adaptive for _, _, adaptive in rows)
    assert any(not static for _, static, _ in rows)
    assert any(static for _, static, _ in rows)


def test_gate_feedback_never_leaks_oracle_information():
    """The retry feedback is returned to the Agent, so it must carry no oracle facts."""
    for scenario in load_scenarios():
        check = validate_result(scenario["id"], static_route(scenario))
        assert not feedback_leaks_oracle(scenario, check["problems"]), scenario["id"]
        assert scenario["oracle"]["decision"] not in " ".join(
            problem for problem in check["problems"] if "expected" in problem
        )


def test_scoring_is_separate_from_the_gate():
    """A well-formed but wrong decision passes the gate and fails the score."""
    scenario = load_scenarios()[0]
    wrong = {
        "decision": "reject",
        "cited_source_ids": [source["id"] for source in scenario["sources"] if source["available"]],
        "tool_path": ["read:policy-primary"],
        "rationale": "deliberately wrong decision with well-formed evidence",
    }
    assert validate_result(scenario["id"], wrong)["status"] == "ready"
    assert score_result(scenario["id"], wrong)["task_success"] is False
    assert score_result(scenario["id"], wrong)["decision_correct"] is False