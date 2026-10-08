import pytest

from looma.optimization.pareto import ParetoFrontier


def test_dominated_candidate_is_removed():
    frontier = ParetoFrontier().add("weak", {"a": 0.5, "b": 0.5})
    frontier = frontier.add("strong", {"a": 0.6, "b": 0.5})

    assert frontier.ids == ("strong",)


def test_complementary_candidates_survive():
    frontier = ParetoFrontier().add("left", {"a": 1.0, "b": 0.0})
    frontier = frontier.add("right", {"a": 0.0, "b": 1.0})

    assert frontier.ids == ("left", "right")


def test_equal_scores_are_sorted_deterministically():
    frontier = ParetoFrontier().add("z", {"a": 1.0}).add("a", {"a": 1.0})

    assert frontier.ids == ("a", "z")


def test_score_dimension_mismatch_is_rejected():
    frontier = ParetoFrontier().add("seed", {"a": 1.0})

    with pytest.raises(ValueError, match="same score dimensions"):
        frontier.add("other", {"b": 1.0})
