import json
from pathlib import Path

from experiments.workloads.sotif_regulatory.dataset import (
    HERE,
    load_benchmark,
)
from experiments.workloads.sotif_regulatory.evaluate import evaluate_item
from experiments.workloads.sotif_regulatory.workflow import validate_prediction


FIXTURE = HERE / "fixtures" / "synthetic_examples.json"


def test_synthetic_regulatory_fixture_is_valid():
    benchmark = load_benchmark(FIXTURE)
    assert benchmark["schema"] == "aep-regulatory-benchmark-v1"
    assert len(benchmark["items"]) == 2


def test_regulatory_acceptance_gate_rejects_unknown_evidence():
    item = load_benchmark(FIXTURE)["items"][0]
    result = {
        "answerability": "answerable",
        "answer": "yes",
        "evidence_ids": ["DOES-NOT-EXIST", "POL-B:4.3"],
        "reasoning_summary": "fixture",
        "confidence": 90,
    }
    check = validate_prediction(item, result)
    assert check["status"] == "revise"
    assert any("unknown evidence" in problem for problem in check["problems"])


def test_regulatory_evaluation_rewards_full_chain_and_abstention():
    benchmark = load_benchmark(FIXTURE)
    answerable = benchmark["items"][0]
    score = evaluate_item(
        answerable,
        {
            "answerability": "answerable",
            "answer": "Yes.",
            "evidence_ids": ["POL-A:2.1", "POL-B:4.3"],
        },
    )
    assert score["task_success"] is True

    unanswerable = benchmark["items"][1]
    score = evaluate_item(
        unanswerable,
        {
            "answerability": "unanswerable",
            "answer": None,
            "evidence_ids": ["POL-C:1.0"],
        },
    )
    assert score["task_success"] is True
