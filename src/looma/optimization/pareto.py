"""Deterministic Pareto tracking for multi-objective candidate scores."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite


def _dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return all(left[name] >= right[name] for name in left) and any(
        left[name] > right[name] for name in left
    )


@dataclass(frozen=True)
class ParetoFrontier:
    """An immutable-by-convention set of non-dominated candidate score vectors."""

    scores: dict[str, dict[str, float]] = field(default_factory=dict)
    ids: tuple[str, ...] = ()
    instance_scores: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    instance_best_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    instance_winners: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)

    def add(
        self,
        candidate_id: str,
        scores: Mapping[str, float],
        *,
        instance_scores: Mapping[str, Mapping[str, float]] | None = None,
    ) -> "ParetoFrontier":
        candidate_scores = _normalize_scores(scores)
        if instance_scores is None:
            if self.instance_best_scores:
                raise ValueError("instance scores are required by this frontier")
            return self._add_objective_frontier(candidate_id, candidate_scores)
        if self.scores and not self.instance_best_scores:
            raise ValueError("cannot mix instance scores with an objective-only frontier")
        if self.scores and any(
            set(existing_scores) != set(candidate_scores)
            for existing_scores in self.scores.values()
        ):
            raise ValueError("candidates must use the same score dimensions")

        normalized_instances = {
            instance_id: _normalize_scores(objectives)
            for instance_id, objectives in instance_scores.items()
        }
        if any(not isinstance(instance_id, str) for instance_id in normalized_instances):
            raise ValueError("instance IDs must be strings")
        if not normalized_instances:
            raise ValueError("instance scores must not be empty")

        best_scores = {
            instance_id: dict(objectives)
            for instance_id, objectives in self.instance_best_scores.items()
        }
        winners = {
            instance_id: {
                objective: tuple(candidate_ids)
                for objective, candidate_ids in objectives.items()
            }
            for instance_id, objectives in self.instance_winners.items()
        }
        candidate_instance_scores = {
            cid: {
                instance_id: dict(objectives)
                for instance_id, objectives in by_instance.items()
            }
            for cid, by_instance in self.instance_scores.items()
        }
        candidate_instance_scores.setdefault(candidate_id, {}).update(
            normalized_instances
        )

        for instance_id, objectives in normalized_instances.items():
            if (
                instance_id in best_scores
                and set(best_scores[instance_id]) != set(objectives)
            ):
                raise ValueError("candidates must use the same objectives per instance")
            for objective, score in objectives.items():
                instance_best = best_scores.setdefault(instance_id, {})
                instance_winners = winners.setdefault(instance_id, {})
                current_best = instance_best.get(objective)
                current_winners = instance_winners.get(objective, ())
                if current_best is None or score > current_best:
                    instance_best[objective] = score
                    instance_winners[objective] = (candidate_id,)
                elif score == current_best:
                    instance_winners[objective] = tuple(
                        sorted(set(current_winners) | {candidate_id})
                    )

        active_ids = {
            cid
            for objectives in winners.values()
            for candidate_ids in objectives.values()
            for cid in candidate_ids
        }
        retained_scores = {
            cid: dict(
                candidate_scores
                if cid == candidate_id
                else self.scores[cid]
            )
            for cid in active_ids
        }
        retained_instance_scores = {
            cid: candidate_instance_scores[cid]
            for cid in active_ids
            if cid in candidate_instance_scores
        }
        return ParetoFrontier(
            scores=retained_scores,
            ids=tuple(sorted(active_ids)),
            instance_scores=retained_instance_scores,
            instance_best_scores=best_scores,
            instance_winners=winners,
        )

    def _add_objective_frontier(
        self,
        candidate_id: str,
        candidate_scores: dict[str, float],
    ) -> "ParetoFrontier":
        if not candidate_scores:
            raise ValueError("score dimensions must not be empty")

        dimensions = set(candidate_scores)
        for existing_scores in self.scores.values():
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
        return ParetoFrontier(scores=retained, ids=ordered_ids)

    def contains(self, candidate_id: str) -> bool:
        return candidate_id in self.scores


def _normalize_scores(scores: Mapping[str, float]) -> dict[str, float]:
    candidate_scores: dict[str, float] = {}
    for name, score in scores.items():
        if not isinstance(name, str):
            raise ValueError("score dimension names must be strings")
        if isinstance(score, bool):
            raise ValueError("scores must be finite numbers")
        try:
            numeric_score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("scores must be finite numbers") from exc
        if not isfinite(numeric_score):
            raise ValueError("scores must be finite numbers")
        candidate_scores[name] = numeric_score
    if not candidate_scores:
        raise ValueError("score dimensions must not be empty")
    return candidate_scores


def select_candidate_id(
    frontier: ParetoFrontier,
    *,
    weights: Mapping[str, float] | None = None,
    selection_index: int | None = None,
) -> str:
    """Select by weighted normalized objective ranks, with stable tie-breaking.

    By default every objective dimension receives equal weight. Normalizing each
    dimension across the current frontier prevents raw score scales from
    silently changing its influence.
    """

    if not frontier.ids:
        raise ValueError("cannot select a candidate from an empty frontier")
    if frontier.instance_winners and selection_index is not None and weights is None:
        if isinstance(selection_index, bool) or not isinstance(selection_index, int):
            raise ValueError("selection_index must be an integer")
        pool = [
            candidate
            for instance_id in sorted(frontier.instance_winners)
            for objective in sorted(frontier.instance_winners[instance_id])
            for candidate in frontier.instance_winners[instance_id][objective]
        ]
        if pool:
            return pool[selection_index % len(pool)]
    dimensions = sorted(next(iter(frontier.scores.values())))
    if weights is None:
        normalized_weights = {dimension: 1.0 for dimension in dimensions}
    else:
        if set(weights) != set(dimensions):
            raise ValueError("selection weights must match the frontier dimensions")
        normalized_weights = {}
        for dimension, weight in weights.items():
            if isinstance(weight, bool):
                raise ValueError("selection weights must be finite and non-negative")
            numeric_weight = float(weight)
            if not isfinite(numeric_weight) or numeric_weight < 0:
                raise ValueError("selection weights must be finite and non-negative")
            normalized_weights[dimension] = numeric_weight
        if sum(normalized_weights.values()) <= 0:
            raise ValueError("at least one selection weight must be positive")

    ranges = {
        dimension: (
            min(frontier.scores[candidate][dimension] for candidate in frontier.ids),
            max(frontier.scores[candidate][dimension] for candidate in frontier.ids),
        )
        for dimension in dimensions
    }
    total_weight = sum(normalized_weights.values())

    def rank(candidate: str) -> float:
        weighted = 0.0
        for dimension in dimensions:
            low, high = ranges[dimension]
            value = frontier.scores[candidate][dimension]
            normalized = 0.5 if high == low else (value - low) / (high - low)
            weighted += normalized_weights[dimension] * normalized
        return weighted / total_weight

    return min(
        frontier.ids,
        key=lambda candidate: (-rank(candidate), candidate),
    )
