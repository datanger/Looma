"""Durable optimization state and program-owned acceptance gates."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..serde import normalize_json
from .pareto import ParetoFrontier, select_candidate_id
from .protocol import Candidate, CandidateProposal, candidate_id


@dataclass(frozen=True)
class OptimizationConfig:
    max_iterations: int
    max_metric_calls: int | None = None
    score_threshold: float | None = None
    no_improvement_patience: int | None = None

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        if self.max_metric_calls is not None and self.max_metric_calls < 0:
            raise ValueError("max_metric_calls must be non-negative")
        if self.no_improvement_patience is not None and self.no_improvement_patience < 1:
            raise ValueError("no_improvement_patience must be positive")


@dataclass(frozen=True)
class OptimizationState:
    seed_candidate: Candidate
    candidates: dict[str, Candidate]
    frontier: ParetoFrontier
    iteration: int
    metric_calls: int
    no_improvement_rounds: int
    status: str
    config: OptimizationConfig
    current_candidate_id: str | None = None
    current_scores: dict[str, float] | None = None

    @classmethod
    def initialize(
        cls,
        seed_candidate: Mapping[str, str],
        *,
        max_iterations: int,
        max_metric_calls: int | None = None,
        score_threshold: float | None = None,
        no_improvement_patience: int | None = None,
    ) -> "OptimizationState":
        seed = dict(seed_candidate)
        seed_id = candidate_id(seed)
        return cls(
            seed_candidate=seed,
            candidates={seed_id: dict(seed)},
            frontier=ParetoFrontier(),
            iteration=0,
            metric_calls=0,
            no_improvement_rounds=0,
            status="running",
            config=OptimizationConfig(
                max_iterations=max_iterations,
                max_metric_calls=max_metric_calls,
                score_threshold=score_threshold,
                no_improvement_patience=no_improvement_patience,
            ),
        )

    @property
    def should_stop(self) -> bool:
        if self.status != "running":
            return True
        if self.iteration >= self.config.max_iterations:
            return True
        if (
            self.config.max_metric_calls is not None
            and self.metric_calls >= self.config.max_metric_calls
        ):
            return True
        if (
            self.config.no_improvement_patience is not None
            and self.no_improvement_rounds >= self.config.no_improvement_patience
        ):
            return True
        if (
            self.config.score_threshold is not None
            and self.current_scores is not None
            and all(score >= self.config.score_threshold for score in self.current_scores.values())
        ):
            return True
        return False

    @property
    def frontier_summary(self) -> dict[str, Any]:
        return normalize_json(
            {
                "candidate_ids": list(self.frontier.ids),
                "scores": self.frontier.scores,
            }
        )

    @property
    def best_candidate_id(self) -> str:
        if not self.frontier.ids:
            return candidate_id(self.seed_candidate)
        return select_candidate_id(self.frontier)

    @property
    def best_candidate(self) -> Candidate:
        return dict(self.candidates[self.best_candidate_id])

    def to_json(self) -> dict[str, Any]:
        return normalize_json(
            {
                "seed_candidate": self.seed_candidate,
                "candidates": self.candidates,
                "frontier": {
                    "scores": self.frontier.scores,
                    "ids": self.frontier.ids,
                },
                "iteration": self.iteration,
                "metric_calls": self.metric_calls,
                "no_improvement_rounds": self.no_improvement_rounds,
                "status": self.status,
                "config": self.config,
                "current_candidate_id": self.current_candidate_id,
                "current_scores": self.current_scores,
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "OptimizationState":
        frontier_value = value["frontier"]
        config_value = value["config"]
        frontier = ParetoFrontier(
            scores={
                str(candidate): {
                    str(name): float(score) for name, score in scores.items()
                }
                for candidate, scores in frontier_value["scores"].items()
            },
            ids=tuple(str(candidate) for candidate in frontier_value["ids"]),
        )
        return cls(
            seed_candidate={str(k): str(v) for k, v in value["seed_candidate"].items()},
            candidates={
                str(candidate): {str(k): str(v) for k, v in candidate_value.items()}
                for candidate, candidate_value in value["candidates"].items()
            },
            frontier=frontier,
            iteration=int(value["iteration"]),
            metric_calls=int(value["metric_calls"]),
            no_improvement_rounds=int(value["no_improvement_rounds"]),
            status=str(value["status"]),
            config=OptimizationConfig(**config_value),
            current_candidate_id=value.get("current_candidate_id"),
            current_scores=(
                {str(k): float(v) for k, v in value["current_scores"].items()}
                if value.get("current_scores") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class AcceptanceResult:
    state: OptimizationState
    accepted: bool
    reason: str
    candidate_id: str | None = None


def _reject(state: OptimizationState, reason: str) -> AcceptanceResult:
    return AcceptanceResult(state=state, accepted=False, reason=reason)


def _normalize_scores(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        raise ValueError("scores must contain at least one dimension")
    normalized: dict[str, float] = {}
    for name, score in scores.items():
        if not isinstance(name, str):
            raise ValueError("score dimension names must be strings")
        if isinstance(score, bool):
            raise ValueError("scores must be numbers")
        try:
            normalized[name] = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("scores must be numbers") from exc
    return normalized


def accept_proposal(
    state: OptimizationState,
    proposal: CandidateProposal,
    *,
    scores: Mapping[str, float],
    parent_scores: Mapping[str, float],
    hard_constraints: Sequence[Callable[[Candidate], bool]] = (),
    metric_calls: int = 0,
    parent_candidate_id: str | None = None,
) -> AcceptanceResult:
    """Apply deterministic gates and return a new state when a candidate is accepted."""

    if state.should_stop:
        return _reject(state, "optimization budget or stop condition is exhausted")
    if metric_calls < 0:
        return _reject(state, "metric_calls must be non-negative")

    try:
        proposed_id = candidate_id(proposal.candidate)
        normalized_scores = _normalize_scores(scores)
        normalized_parent_scores = _normalize_scores(parent_scores)
    except ValueError as exc:
        return _reject(state, str(exc))
    except Exception as exc:
        return _reject(state, str(exc))

    known_components = set(state.seed_candidate)
    if not set(proposal.components_to_update).issubset(known_components):
        return _reject(state, "proposal updates an unknown component")
    if set(proposal.candidate) != known_components:
        return _reject(state, "proposal candidate must preserve the configured components")
    if set(normalized_scores) != set(normalized_parent_scores):
        return _reject(state, "candidate and parent must use the same score dimensions")
    parent_id = parent_candidate_id or state.current_candidate_id or candidate_id(state.seed_candidate)
    if parent_candidate_id is not None and parent_id not in state.candidates:
        return _reject(state, "parent candidate is not registered")
    if state.current_scores is not None and parent_id == state.current_candidate_id and normalized_parent_scores != state.current_scores:
        return _reject(state, "parent scores do not match the current optimization state")
    if proposed_id in state.candidates:
        return _reject(state, "candidate has already been evaluated")

    try:
        for constraint in hard_constraints:
            if not constraint(proposal.candidate):
                return _reject(state, "proposal failed a hard constraint")
    except Exception as exc:
        return _reject(state, f"hard constraint failed: {exc}")

    frontier = state.frontier
    if not frontier.scores:
        frontier = frontier.add(parent_id, normalized_parent_scores)
    elif parent_id not in frontier.scores:
        return _reject(state, "parent candidate is not present in the frontier")

    next_frontier = frontier.add(proposed_id, normalized_scores)
    if proposed_id not in next_frontier.scores:
        return _reject(state, "candidate is dominated by the current frontier")

    next_candidates = {
        candidate: dict(value) for candidate, value in state.candidates.items()
    }
    next_candidates[proposed_id] = dict(proposal.candidate)
    improved = any(
        normalized_scores[name] > normalized_parent_scores[name]
        for name in normalized_scores
    )
    next_state = OptimizationState(
        seed_candidate=dict(state.seed_candidate),
        candidates=next_candidates,
        frontier=next_frontier,
        iteration=state.iteration + 1,
        metric_calls=state.metric_calls + metric_calls,
        no_improvement_rounds=0 if improved else state.no_improvement_rounds + 1,
        status="running",
        config=state.config,
        current_candidate_id=proposed_id,
        current_scores=normalized_scores,
    )
    if next_state.should_stop:
        next_state = OptimizationState(
            seed_candidate=next_state.seed_candidate,
            candidates=next_state.candidates,
            frontier=next_state.frontier,
            iteration=next_state.iteration,
            metric_calls=next_state.metric_calls,
            no_improvement_rounds=next_state.no_improvement_rounds,
            status="complete",
            config=next_state.config,
            current_candidate_id=next_state.current_candidate_id,
            current_scores=next_state.current_scores,
        )
    return AcceptanceResult(
        state=next_state,
        accepted=True,
        reason="accepted",
        candidate_id=proposed_id,
    )


def initialize(
    seed_candidate: Mapping[str, str],
    *,
    max_iterations: int,
    max_metric_calls: int | None = None,
    score_threshold: float | None = None,
    no_improvement_patience: int | None = None,
) -> OptimizationState:
    """Create an optimization state through the package-level public API."""

    return OptimizationState.initialize(
        seed_candidate,
        max_iterations=max_iterations,
        max_metric_calls=max_metric_calls,
        score_threshold=score_threshold,
        no_improvement_patience=no_improvement_patience,
    )


def select_candidate(state: OptimizationState) -> Candidate:
    """Return the deterministically selected frontier candidate or the seed."""

    return dict(state.best_candidate)
