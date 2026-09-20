import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_module(*args: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_freeze_subset_is_order_independent(tmp_path: Path):
    questions = [
        {"qid": "q1", "question": "one"},
        {"qid": "q2", "question": "two"},
        {"qid": "q3", "question": "three"},
        {"qid": "q4", "question": "four"},
    ]
    source_a = tmp_path / "a.json"
    source_b = tmp_path / "b.json"
    source_a.write_text(json.dumps(questions), encoding="utf-8")
    source_b.write_text(json.dumps(list(reversed(questions))), encoding="utf-8")

    selected = []
    for name, source in (("a", source_a), ("b", source_b)):
        output = tmp_path / f"{name}-subset.json"
        manifest = tmp_path / f"{name}-manifest.json"
        result = run_module(
            "-m",
            "experiments.case_studies.arag_host_native.freeze_subset",
            "--questions",
            str(source),
            "--size",
            "2",
            "--seed",
            "fixed",
            "--output",
            str(output),
            "--manifest",
            str(manifest),
        )
        assert result.returncode == 0, result.stderr
        selected.append(
            json.loads(manifest.read_text(encoding="utf-8"))["selected_qids"]
        )
    assert selected[0] == selected[1]


def test_paired_prediction_comparison(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    aep = tmp_path / "aep.jsonl"
    output = tmp_path / "comparison.json"
    write_jsonl(
        baseline,
        [
            {"qid": "1", "gold_answer": "Paris", "pred_answer": "Paris", "total_retrieved_tokens": 100},
            {"qid": "2", "gold_answer": "Berlin", "pred_answer": "Munich", "total_retrieved_tokens": 200},
        ],
    )
    write_jsonl(
        aep,
        [
            {"qid": "1", "gold_answer": "Paris", "pred_answer": "Paris, France", "total_retrieved_tokens": 80, "tool_path": ["keyword", "read"]},
            {"qid": "2", "gold_answer": "Berlin", "pred_answer": "Berlin", "total_retrieved_tokens": 150, "tool_path": ["semantic", "read"]},
        ],
    )
    result = run_module(
        "-m",
        "experiments.case_studies.arag_host_native.compare_predictions",
        "--baseline",
        str(baseline),
        "--aep",
        str(aep),
        "--bootstrap",
        "100",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["paired_questions"] == 2
    assert payload["baseline"]["contain_accuracy"] == 0.5
    assert payload["aep"]["contain_accuracy"] == 1.0
    assert payload["mcnemar_contain"]["aep_only_correct"] == 1


def test_arag_run_manifest_hashes_inputs(tmp_path: Path):
    files = {}
    for name in ("questions.json", "chunks.json", "config.yaml", "predictions.jsonl"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        files[name] = path

    output = tmp_path / "manifest.json"
    result = run_module(
        "-m",
        "experiments.case_studies.arag_host_native.run_manifest",
        "--mode",
        "aep-host-native",
        "--dataset",
        "tiny",
        "--questions",
        str(files["questions.json"]),
        "--chunks",
        str(files["chunks.json"]),
        "--config",
        str(files["config.yaml"]),
        "--predictions",
        str(files["predictions.jsonl"]),
        "--arag-commit",
        "a44de6b",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["questions"]["sha256"]
    assert payload["predictions"]["sha256"]
