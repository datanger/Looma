"""A deterministic AEP + GEPA-style reflective optimization example."""

from __future__ import annotations

import json
from typing import Any

from looma import step, workflow
from looma.optimization.engine import request_reflection
from looma.optimization.protocol import Candidate, EvaluationBatch
from looma.optimization.state import OptimizationState, accept_proposal


class DeterministicAdapter:
    """Score whether a candidate explicitly asks for evidence."""

    def evaluate(
        self,
        batch: list[dict[str, str]],
        candidate: Candidate,
        capture_traces: bool = False,
    ) -> EvaluationBatch:
        has_evidence_guidance = "cite evidence" in candidate["instruction"].lower()
        score = 1.0 if has_evidence_guidance else 0.5
        trace = {
            "failure": None if has_evidence_guidance else "missing evidence guidance",
            "candidate_instruction": candidate["instruction"],
        }
        return EvaluationBatch(
            outputs=[{"score": score} for _ in batch],
            scores=[score for _ in batch],
            trajectories=[trace for _ in batch] if capture_traces else None,
            side_information=[trace for _ in batch],
            metric_calls=len(batch),
        )

    def make_reflective_dataset(
        self,
        candidate: Candidate,
        evaluation: EvaluationBatch,
        components_to_update: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "examples": [
                {
                    "candidate": candidate,
                    "evaluation": evaluation.to_json(),
                    "components_to_update": components_to_update,
                }
            ]
        }


ADAPTER = DeterministicAdapter()
DATASET = [{"question": "What evidence supports this answer?"}]


@workflow
def main() -> None:
    state = OptimizationState.initialize(
        {"instruction": "Answer directly."},
        max_iterations=3,
    )
    evaluation = step(ADAPTER.evaluate, DATASET, state.seed_candidate, capture_traces=True)
    proposal = request_reflection(
        task=(
            "Analyze the evaluation traces and propose a candidate update. "
            "Improve the instruction component while preserving its scope."
        ),
        candidate=state.seed_candidate,
        evaluation=evaluation,
        frontier_ids=state.frontier.ids,
        metric_calls=evaluation["metric_calls"],
        remaining_budget=10 - evaluation["metric_calls"],
    )
    accepted = step(
        accept_proposal,
        state,
        proposal,
        scores={"example": 1.0},
        parent_scores={"example": 0.5},
        metric_calls=evaluation["metric_calls"],
    )
    if not accepted["accepted"]:
        raise RuntimeError(accepted["reason"])

    result = {
        "accepted": accepted["accepted"],
        "candidate": accepted["state"]["candidates"][accepted["candidate_id"]],
        "frontier": accepted["state"]["frontier"]["ids"],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
