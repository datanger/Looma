from dataclasses import replace

import pytest

from looma.optimization import CandidateProposal, candidate_id, select_candidate
from looma.optimization.state import OptimizationConfig, OptimizationState, accept_proposal


def test_state_round_trip_is_json_compatible():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)

    assert OptimizationState.from_json(state.to_json()) == state


def test_unknown_component_does_not_mutate_state():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"other": "bad"}, ["other"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.0},
    )

    assert result.accepted is False
    assert result.state == state


def test_hard_constraint_rejects_higher_score():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "unsafe"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
        hard_constraints={"prompt_is_safe": False},
    )

    assert result.accepted is False
    assert result.state == state


def test_nondominated_proposal_updates_budget_and_frontier():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "improved"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
        metric_calls=2,
    )

    assert result.accepted is True
    assert result.state.iteration == 1
    assert result.state.metric_calls == 2
    assert result.candidate_id in result.state.frontier.ids
    assert result.state.candidates[result.candidate_id]["prompt"] == "improved"


def test_acceptance_tracks_per_instance_scores_and_winner_frontier():
    state = OptimizationState.initialize({"prompt": "seed"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "improved"}, ["prompt"]),
        scores={"quality": 0.75},
        parent_scores={"quality": 0.5},
        parent_instance_scores={"case-a": {"quality": 0.0}, "case-b": {"quality": 1.0}},
        instance_scores={"case-a": {"quality": 1.0}, "case-b": {"quality": 0.0}},
    )

    assert result.accepted
    assert set(result.state.frontier.ids) == {
        candidate_id({"prompt": "seed"}),
        candidate_id({"prompt": "improved"}),
    }
    assert result.state.frontier.instance_winners["case-a"]["quality"] == (
        candidate_id({"prompt": "improved"}),
    )
    restored = OptimizationState.from_json(result.state.to_json())
    assert restored == result.state
    assert select_candidate(restored) == select_candidate(result.state)


def test_instance_level_improvement_resets_no_improvement_patience():
    state = replace(
        OptimizationState.initialize(
            {"prompt": "seed"},
            max_iterations=4,
            no_improvement_patience=3,
        ),
        no_improvement_rounds=1,
    )
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "specialist"}, ["prompt"]),
        scores={"quality": 0.5},
        parent_scores={"quality": 0.5},
        parent_instance_scores={"case-a": {"quality": 0.0}},
        instance_scores={"case-a": {"quality": 1.0}},
    )

    assert result.accepted
    assert result.state.no_improvement_rounds == 0


def test_exhausted_metric_budget_rejects_without_mutation():
    state = replace(
        OptimizationState.initialize({"prompt": "start"}, max_iterations=3),
        config=OptimizationConfig(max_iterations=3, max_metric_calls=0),
    )
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "improved"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
    )

    assert result.accepted is False
    assert result.state == state


def test_fractional_metric_calls_cannot_bypass_integer_budget_accounting():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "improved"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
        metric_calls=0.5,
    )

    assert result.accepted is False
    assert "metric_calls" in result.reason
    assert result.state == state


def test_optimization_config_rejects_non_finite_threshold():
    with pytest.raises(ValueError, match="finite"):
        OptimizationState.initialize(
            {"prompt": "start"},
            max_iterations=3,
            score_threshold=float("nan"),
        )


def test_parent_scores_must_match_current_state():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    first = accept_proposal(
        state,
        CandidateProposal({"prompt": "first"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
    )
    second = accept_proposal(
        first.state,
        CandidateProposal({"prompt": "second"}, ["prompt"]),
        scores={"case": 1.5},
        parent_scores={"case": 0.0},
    )

    assert second.accepted is False
    assert second.state == first.state


def test_proposal_cannot_change_undeclared_components():
    state = OptimizationState.initialize(
        {"prompt": "start", "policy": "safe"}, max_iterations=3
    )
    result = accept_proposal(
        state,
        CandidateProposal(
            {"prompt": "better", "policy": "unsafe"},
            ["prompt"],
        ),
        scores={"quality": 1.0},
        parent_scores={"quality": 0.0},
    )

    assert result.accepted is False
    assert "undeclared" in result.reason
    assert result.state == state


def test_proposal_cannot_exceed_metric_call_budget():
    state = OptimizationState.initialize(
        {"prompt": "start"}, max_iterations=3, max_metric_calls=1
    )
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "better"}, ["prompt"]),
        scores={"quality": 1.0},
        parent_scores={"quality": 0.0},
        metric_calls=2,
    )

    assert result.accepted is False
    assert "metric-call budget" in result.reason
    assert result.state == state


def test_metric_budget_can_be_checked_before_running_an_evaluation():
    state = OptimizationState.initialize(
        {"prompt": "start"}, max_iterations=3, max_metric_calls=4
    )

    assert state.can_evaluate(metric_calls=2)
    assert not state.can_evaluate(metric_calls=2, pending_metric_calls=3)


def test_serializable_hard_constraint_results_are_enforced():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "unsafe"}, ["prompt"]),
        scores={"quality": 1.0},
        parent_scores={"quality": 0.0},
        hard_constraints={"forbid_unsafe_prompt": False},
    )

    assert result.accepted is False
    assert "forbid_unsafe_prompt" in result.reason
