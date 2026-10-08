"""A deterministic AEP + GEPA-style reflective optimization example."""

from __future__ import annotations

import json
from typing import Any

from looma import step, workflow
from looma.optimization import candidate_id, select_candidate
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
            instance_scores={item["id"]: {"quality": score} for item in batch},
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
DATASET = [
    {
        "id": "evidence-question-1",
        "question": "What evidence supports this answer?",
    }
]


@workflow
def main() -> None:
    state = OptimizationState.initialize(
        {"instruction": "Answer directly."},
        max_iterations=3,
        max_metric_calls=10,
        score_threshold=1.0,
    )
    while not state.should_stop:
        expected_calls = 2 * len(DATASET)
        if not state.can_evaluate(metric_calls=expected_calls):
            break

        parent = select_candidate(state)
        parent_id = candidate_id(parent)
        parent_evaluation = step(
            ADAPTER.evaluate,
            DATASET,
            parent,
            capture_traces=True,
        )
        proposal = request_reflection(
            task=(
                "Analyze the evaluation traces and propose a candidate update. "
                "Improve the instruction component while preserving its scope."
            ),
            candidate=parent,
            evaluation=parent_evaluation,
            components_to_update=["instruction"],
            frontier_ids=state.frontier.ids,
            metric_calls=parent_evaluation["metric_calls"],
            remaining_budget=10 - state.metric_calls - parent_evaluation["metric_calls"],
        )
        proposal_evaluation = step(
            ADAPTER.evaluate,
            DATASET,
            proposal.candidate,
            capture_traces=True,
        )
        accepted = step(
            accept_proposal,
            state,
            proposal,
            scores={"example": proposal_evaluation["scores"][0]},
            parent_scores={"example": parent_evaluation["scores"][0]},
            instance_scores=proposal_evaluation["instance_scores"],
            parent_instance_scores=parent_evaluation["instance_scores"],
            metric_calls=(
                parent_evaluation["metric_calls"]
                + proposal_evaluation["metric_calls"]
            ),
            parent_candidate_id=parent_id,
        )
        if not accepted["accepted"]:
            raise RuntimeError(accepted["reason"])
        state = OptimizationState.from_json(accepted["state"])

    result = {
        "accepted": accepted["accepted"],
        "candidate": state.best_candidate,
        "frontier": list(state.frontier.ids),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
