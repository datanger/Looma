"""Host-native reflective optimization primitives for AEP workflows."""

from .protocol import (
    Candidate,
    CandidateProposal,
    EvaluationBatch,
    OptimizationAdapter,
    candidate_id,
)

__all__ = [
    "Candidate",
    "CandidateProposal",
    "EvaluationBatch",
    "OptimizationAdapter",
    "candidate_id",
]
