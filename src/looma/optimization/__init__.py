"""Host-native reflective optimization primitives for AEP workflows."""

from .protocol import (
    Candidate,
    CandidateProposal,
    EvaluationBatch,
    OptimizationAdapter,
    candidate_id,
)
from .engine import build_reflection_input, request_reflection
from .pareto import ParetoFrontier, select_candidate_id
from .schema import candidate_proposal_schema, reflection_input_schema
from .state import (
    AcceptanceResult,
    OptimizationConfig,
    OptimizationState,
    accept_proposal,
    initialize,
    select_candidate,
)

__all__ = [
    "Candidate",
    "CandidateProposal",
    "EvaluationBatch",
    "OptimizationAdapter",
    "candidate_id",
    "build_reflection_input",
    "request_reflection",
    "ParetoFrontier",
    "select_candidate_id",
    "OptimizationConfig",
    "OptimizationState",
    "AcceptanceResult",
    "accept_proposal",
    "initialize",
    "select_candidate",
    "candidate_proposal_schema",
    "reflection_input_schema",
]
