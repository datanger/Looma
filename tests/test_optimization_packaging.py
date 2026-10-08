from importlib.resources import files

import looma.optimization as optimization


def test_optimization_public_exports_are_explicit():
    assert "CandidateProposal" in optimization.__all__
    assert "request_reflection" in optimization.__all__


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
