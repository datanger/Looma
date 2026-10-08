import pytest

from looma.optimization.pareto import ParetoFrontier, select_candidate_id


def test_dominated_candidate_is_removed():
    frontier = ParetoFrontier().add("weak", {"a": 0.5, "b": 0.5})
    frontier = frontier.add("strong", {"a": 0.6, "b": 0.5})

    assert frontier.ids == ("strong",)


def test_complementary_candidates_survive():
    frontier = ParetoFrontier().add("left", {"a": 1.0, "b": 0.0})
    frontier = frontier.add("right", {"a": 0.0, "b": 1.0})

    assert frontier.ids == ("left", "right")


def test_instance_winners_preserve_candidates_that_win_different_examples():
    frontier = ParetoFrontier().add(
        "candidate-a",
        {"quality": 0.75},
        instance_scores={
            "case-1": {"quality": 1.0},
            "case-2": {"quality": 1.0},
            "case-3": {"quality": 0.0},
        },
    )
    frontier = frontier.add(
        "candidate-b",
        {"quality": 0.75},
        instance_scores={
            "case-1": {"quality": 0.0},
            "case-2": {"quality": 0.0},
            "case-3": {"quality": 1.0},
        },
    )

    assert frontier.ids == ("candidate-a", "candidate-b")
    assert frontier.instance_winners["case-3"]["quality"] == ("candidate-b",)


def test_instance_selection_frequency_is_deterministic_and_proportional():
    frontier = ParetoFrontier().add(
        "candidate-a",
        {"quality": 0.75},
        instance_scores={
            "case-1": {"quality": 1.0},
            "case-2": {"quality": 1.0},
            "case-3": {"quality": 0.0},
        },
    )
    frontier = frontier.add(
        "candidate-b",
        {"quality": 0.75},
        instance_scores={
            "case-1": {"quality": 0.0},
            "case-2": {"quality": 0.0},
            "case-3": {"quality": 1.0},
        },
    )

    first = [select_candidate_id(frontier, selection_index=i) for i in range(3)]
    second = [select_candidate_id(frontier, selection_index=i) for i in range(3)]

    assert first == second
    assert first.count("candidate-a") == 2
    assert first.count("candidate-b") == 1


def test_equal_scores_are_sorted_deterministically():
    frontier = ParetoFrontier().add("z", {"a": 1.0}).add("a", {"a": 1.0})

    assert frontier.ids == ("a", "z")


def test_score_dimension_mismatch_is_rejected():
    frontier = ParetoFrontier().add("seed", {"a": 1.0})

    with pytest.raises(ValueError, match="same score dimensions"):
        frontier.add("other", {"b": 1.0})


@pytest.mark.parametrize("score", [float("nan"), float("inf"), True])
def test_non_finite_or_boolean_scores_are_rejected(score):
    with pytest.raises(ValueError, match="finite numbers"):
        ParetoFrontier().add("candidate", {"quality": score})


def test_default_selection_is_invariant_to_objective_scale():
    original = ParetoFrontier().add("accuracy-heavy", {"accuracy": 100, "latency": 0})
    original = original.add("latency-heavy", {"accuracy": 80, "latency": 9})
    scaled = ParetoFrontier().add("accuracy-heavy", {"accuracy": 100, "latency": 0})
    scaled = scaled.add("latency-heavy", {"accuracy": 80, "latency": 900})

    assert select_candidate_id(original) == select_candidate_id(scaled)


def test_selection_weights_change_tradeoff_deterministically():
    frontier = ParetoFrontier().add("accuracy-heavy", {"accuracy": 100, "latency": 0})
    frontier = frontier.add("latency-heavy", {"accuracy": 80, "latency": 9})

    assert select_candidate_id(frontier, weights={"accuracy": 4, "latency": 1}) == "accuracy-heavy"
    assert select_candidate_id(frontier, weights={"accuracy": 1, "latency": 4}) == "latency-heavy"


@pytest.mark.parametrize(
    "weights",
    [
        {"accuracy": 1},
        {"accuracy": -1, "latency": 1},
        {"accuracy": float("nan"), "latency": 1},
        {"accuracy": 0, "latency": 0},
    ],
)
def test_selection_rejects_invalid_weights(weights):
    frontier = ParetoFrontier().add("candidate", {"accuracy": 1, "latency": 1})

    with pytest.raises(ValueError):
        select_candidate_id(frontier, weights=weights)
