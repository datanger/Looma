from importlib.resources import files

import looma.optimization as optimization
from looma.optimization.schema import candidate_proposal_schema, reflection_input_schema


def test_optimization_public_exports_are_explicit():
    assert "CandidateProposal" in optimization.__all__
    assert "request_reflection" in optimization.__all__
    assert "OptimizationState" in optimization.__all__
    assert "ParetoFrontier" in optimization.__all__


def test_reflection_and_proposal_schemas_are_structural():
    proposal_schema = candidate_proposal_schema()
    reflection_schema = reflection_input_schema()

    assert proposal_schema["type"] == "object"
    assert reflection_schema["required"] == [
        "candidate",
        "components_to_update",
        "evaluation",
        "frontier",
        "budget",
    ]


def test_packaged_skill_describes_host_native_gepa_capability():
    skill = files("looma").joinpath("skills", "agent-embedded-programming", "SKILL.md")
    text = skill.read_text(encoding="utf-8")

    for phrase in (
        "candidate evaluation",
        "ASI",
        "Pareto frontier",
        "agent()",
        "direct model",
    ):
        assert phrase in text
