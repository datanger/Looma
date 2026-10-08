"""Deterministic Pareto tracking for multi-objective candidate scores."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


def _dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return all(left[name] >= right[name] for name in left) and any(
        left[name] > right[name] for name in left
    )


@dataclass(frozen=True)
class ParetoFrontier:
    """An immutable-by-convention set of non-dominated candidate score vectors."""

    scores: dict[str, dict[str, float]] = field(default_factory=dict)
    ids: tuple[str, ...] = ()

    def add(self, candidate_id: str, scores: Mapping[str, float]) -> "ParetoFrontier":
        candidate_scores = dict(scores)
        if not candidate_scores:
            raise ValueError("score dimensions must not be empty")

        dimensions = set(candidate_scores)
        for existing_id, existing_scores in self.scores.items():
            if set(existing_scores) != dimensions:
                raise ValueError("candidates must use the same score dimensions")
            if _dominates(existing_scores, candidate_scores):
                return self

        retained = {
            existing_id: dict(existing_scores)
            for existing_id, existing_scores in self.scores.items()
            if not _dominates(candidate_scores, existing_scores)
        }
        retained[candidate_id] = candidate_scores
        ordered_ids = tuple(sorted(retained))
        return ParetoFrontier(
            scores=retained,
            ids=ordered_ids,
        )

    def contains(self, candidate_id: str) -> bool:
        return candidate_id in self.scores


def select_candidate_id(frontier: ParetoFrontier) -> str:
    """Select a deterministic frontier member, preferring higher scores."""

    if not frontier.ids:
        raise ValueError("cannot select a candidate from an empty frontier")
    dimensions = sorted(next(iter(frontier.scores.values())))
    return min(
        frontier.ids,
        key=lambda candidate: tuple(
            [-sum(frontier.scores[candidate].values())]
            + [-frontier.scores[candidate][dimension] for dimension in dimensions]
            + [candidate]
        ),
    )
