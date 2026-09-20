from experiments.workloads.bounded_autonomy.environment import load_scenarios
from experiments.workloads.bounded_autonomy.sanity import adaptive_oracle, static_route
from experiments.workloads.bounded_autonomy.validator import validate_result


def test_bounded_autonomy_suite_has_real_perturbations():
    rows = []
    for scenario in load_scenarios():
        static_ok = validate_result(
            scenario["id"],
            static_route(scenario),
        )["status"] == "ready"
        adaptive_ok = validate_result(
            scenario["id"],
            adaptive_oracle(scenario),
        )["status"] == "ready"
        rows.append((scenario["id"], static_ok, adaptive_ok))

    assert all(adaptive for _, _, adaptive in rows)
    assert any(not static for _, static, _ in rows)
    assert any(static for _, static, _ in rows)
