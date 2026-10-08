"""Host-native reflective optimization primitives for AEP workflows."""

from .protocol import (
    Candidate,
    CandidateProposal,
    EvaluationBatch,
    OptimizationAdapter,
    candidate_id,
)
from .engine import build_reflection_input, request_reflection

__all__ = [
    "Candidate",
    "CandidateProposal",
    "EvaluationBatch",
    "OptimizationAdapter",
    "candidate_id",
    "build_reflection_input",
    "request_reflection",
]
