from dataclasses import replace

from looma.optimization import CandidateProposal
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
        hard_constraints=[lambda candidate: candidate["prompt"] != "unsafe"],
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
