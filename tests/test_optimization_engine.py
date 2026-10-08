from looma.optimization import CandidateProposal, EvaluationBatch
from looma.optimization.engine import build_reflection_input, request_reflection


def test_reflection_payload_contains_asi_and_budget():
    payload = build_reflection_input(
        candidate={"prompt": "start"},
        evaluation=EvaluationBatch(
            outputs=["bad"],
            scores=[0.0],
            trajectories=[{"error": "missing evidence"}],
            side_information=[{"error": "missing evidence"}],
        ),
        frontier_ids=["seed"],
        metric_calls=4,
        remaining_budget=6,
        components_to_update=["prompt"],
    )

    assert payload["evaluation"]["side_information"][0]["error"] == "missing evidence"
    assert payload["budget"]["remaining_metric_calls"] == 6
    assert payload["components_to_update"] == ["prompt"]


def test_request_reflection_delegates_to_agent(monkeypatch):
    seen = {}

    def fake_agent(**kwargs):
        seen.update(kwargs)
        return CandidateProposal({"prompt": "updated"}, ["prompt"])

    monkeypatch.setattr("looma.optimization.engine.agent", fake_agent)
    proposal = request_reflection(
        task="Improve the prompt.",
        candidate={"prompt": "start"},
        evaluation=EvaluationBatch(outputs=["bad"], scores=[0.0]),
        frontier_ids=["seed"],
        metric_calls=1,
        remaining_budget=9,
    )

    assert proposal.candidate["prompt"] == "updated"
    assert seen["output_schema"] is CandidateProposal
