import pytest

from looma import SerializationError
from looma.optimization import CandidateProposal, EvaluationBatch, candidate_id


def test_candidate_id_is_stable_for_mapping_order():
    assert candidate_id({"b": "B", "a": "A"}) == candidate_id({"a": "A", "b": "B"})


def test_candidate_proposal_normalizes_to_json():
    proposal = CandidateProposal(
        candidate={"system_prompt": "Use evidence."},
        components_to_update=["system_prompt"],
        rationale="The previous candidate omitted evidence checks.",
    )

    assert proposal.to_json()["candidate"]["system_prompt"] == "Use evidence."


def test_candidate_id_rejects_non_string_values():
    with pytest.raises(SerializationError):
        candidate_id({"prompt": 3})


def test_evaluation_batch_requires_aligned_values():
    with pytest.raises(ValueError, match="same length"):
        EvaluationBatch(outputs=["ok"], scores=[])
