"""Host-native reflection helpers for explicit AEP optimization loops."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..api import agent
from ..serde import normalize_json
from .protocol import Candidate, CandidateProposal, EvaluationBatch


def build_reflection_input(
    *,
    candidate: Candidate,
    evaluation: EvaluationBatch,
    frontier_ids: Sequence[str],
    metric_calls: int,
    remaining_budget: int | None,
) -> dict[str, Any]:
    """Build a JSON-compatible reflection payload without invoking a model."""

    if metric_calls < 0:
        raise ValueError("metric_calls must be non-negative")
    if remaining_budget is not None and remaining_budget < 0:
        raise ValueError("remaining_budget must be non-negative or None")

    return normalize_json(
        {
            "candidate": candidate,
            "evaluation": evaluation,
            "frontier": {"candidate_ids": list(frontier_ids)},
            "budget": {
                "metric_calls": metric_calls,
                "remaining_metric_calls": remaining_budget,
            },
        }
    )


def request_reflection(
    *,
    task: str,
    candidate: Candidate,
    evaluation: EvaluationBatch,
    frontier_ids: Sequence[str],
    metric_calls: int,
    remaining_budget: int | None,
) -> CandidateProposal:
    """Delegate semantic candidate reflection to the current Host Agent."""

    payload = build_reflection_input(
        candidate=candidate,
        evaluation=evaluation,
        frontier_ids=frontier_ids,
        metric_calls=metric_calls,
        remaining_budget=remaining_budget,
    )
    return agent(task=task, input=payload, output_schema=CandidateProposal)
