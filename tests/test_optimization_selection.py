from looma.optimization import (
    CandidateProposal,
    OptimizationState,
    candidate_id,
    initialize,
    select_candidate,
)
from looma.optimization.state import accept_proposal


def test_select_candidate_returns_seed_before_first_evaluation():
    state = initialize({"prompt": "seed"}, max_iterations=3)

    assert select_candidate(state) == {"prompt": "seed"}
    assert state.frontier_summary["candidate_ids"] == []
    assert state.best_candidate == {"prompt": "seed"}


def test_select_candidate_is_deterministic_across_complementary_frontier():
    state = OptimizationState.initialize({"prompt": "seed"}, max_iterations=4)
    left = accept_proposal(
        state,
        CandidateProposal({"prompt": "left"}, ["prompt"]),
        scores={"quality": 2.0, "coverage": 0.0},
        parent_scores={"quality": 0.0, "coverage": 0.0},
    )
    right = accept_proposal(
        left.state,
        CandidateProposal({"prompt": "right"}, ["prompt"]),
        scores={"quality": 0.0, "coverage": 1.0},
        parent_scores={"quality": 2.0, "coverage": 0.0},
        parent_candidate_id=left.candidate_id,
    )

    assert right.accepted is True
    assert len(right.state.frontier.ids) == 2
    assert select_candidate(right.state) == {"prompt": "left"}
    assert right.state.best_candidate_id == candidate_id({"prompt": "left"})
