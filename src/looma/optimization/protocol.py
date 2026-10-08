"""Serializable contracts shared by AEP optimization workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from ..exceptions import SerializationError
from ..serde import json_hash, normalize_json


Candidate: TypeAlias = dict[str, str]


def _canonical_candidate(candidate: Mapping[str, str]) -> Candidate:
    if not isinstance(candidate, Mapping):
        raise SerializationError("candidate must be a mapping of string components")

    normalized: Candidate = {}
    for key, value in candidate.items():
        if not isinstance(key, str):
            raise SerializationError("candidate component names must be strings")
        if not isinstance(value, str):
            raise SerializationError("candidate component values must be strings")
        normalized[key] = value
    return dict(sorted(normalized.items()))


def candidate_id(candidate: Mapping[str, str]) -> str:
    """Return a stable content identity for a textual candidate."""

    return json_hash(_canonical_candidate(candidate))[:24]


@dataclass(frozen=True)
class EvaluationBatch:
    """Evaluation outputs, scores, and optional GEPA reflection evidence."""

    outputs: list[Any]
    scores: list[float]
    trajectories: list[Any] | None = None
    objective_scores: list[dict[str, float]] | None = None
    side_information: list[Any] | None = None
    metric_calls: int | None = None
    instance_scores: dict[str, dict[str, float]] | None = None

    def __post_init__(self) -> None:
        size = len(self.outputs)
        if len(self.scores) != size:
            raise ValueError("outputs and scores must have the same length")

        for name in ("trajectories", "objective_scores", "side_information"):
            values = getattr(self, name)
            if values is not None and len(values) != size:
                raise ValueError(f"outputs and {name} must have the same length")

        if self.instance_scores is not None:
            if any(
                not isinstance(instance_id, str) or not instance_id
                for instance_id in self.instance_scores
            ):
                raise ValueError("instance score IDs must be non-empty strings")
            if not self.instance_scores:
                raise ValueError("instance scores must not be empty")
            if any(not scores for scores in self.instance_scores.values()):
                raise ValueError("each instance must have at least one objective score")

        if self.metric_calls is not None and self.metric_calls < 0:
            raise ValueError("metric_calls must be non-negative")

    def to_json(self) -> dict[str, Any]:
        return normalize_json(
            {
                "outputs": self.outputs,
                "scores": self.scores,
                "trajectories": self.trajectories,
                "objective_scores": self.objective_scores,
                "instance_scores": self.instance_scores,
                "side_information": self.side_information,
                "metric_calls": self.metric_calls,
            }
        )


@dataclass(frozen=True)
class CandidateProposal:
    """A Host Agent's proposed textual candidate mutation."""

    candidate: Candidate
    components_to_update: list[str]
    rationale: str = ""
    hypothesis: str = ""
    targeted_failure: str = ""

    def __post_init__(self) -> None:
        _canonical_candidate(self.candidate)
        if any(not isinstance(component, str) for component in self.components_to_update):
            raise SerializationError("components_to_update values must be strings")

    def to_json(self) -> dict[str, Any]:
        return normalize_json(
            {
                "candidate": self.candidate,
                "components_to_update": self.components_to_update,
                "rationale": self.rationale,
                "hypothesis": self.hypothesis,
                "targeted_failure": self.targeted_failure,
            }
        )


class OptimizationAdapter(Protocol):
    """Application-owned evaluator and reflection-dataset builder."""

    def evaluate(
        self, batch: list[Any], candidate: Candidate, capture_traces: bool = False
    ) -> EvaluationBatch:
        raise NotImplementedError

    def make_reflective_dataset(
        self,
        candidate: Candidate,
        evaluation: EvaluationBatch,
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        raise NotImplementedError
