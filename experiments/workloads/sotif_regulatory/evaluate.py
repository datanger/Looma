from __future__ import annotations

import argparse
import json
import re
import string
from pathlib import Path

from experiments.workloads.sotif_regulatory.dataset import load_benchmark


def normalize(text) -> str:
    value = "" if text is None else str(text).lower()
    value = "".join(ch for ch in value if ch not in set(string.punctuation))
    return " ".join(value.split())


def evaluate_item(item: dict, prediction: dict) -> dict:
    predicted_answerable = prediction.get("answerability") == "answerable"
    answerability_correct = predicted_answerable == bool(item["answerable"])

    cited = set(prediction.get("evidence_ids") or [])
    gold = set(item["gold_evidence_ids"])
    evidence_recall = 1.0 if not gold else len(cited & gold) / len(gold)
    evidence_precision = 1.0 if not cited else len(cited & gold) / len(cited)

    if item["answerable"]:
        answer_match = int(
            normalize(item.get("gold_answer"))
            in normalize(prediction.get("answer"))
        )
    else:
        answer_match = int(
            prediction.get("answerability") == "unanswerable"
            and not str(prediction.get("answer") or "").strip()
        )

    hops = len(prediction.get("evidence_ids") or [])
    hop_requirement_met = (
        hops >= int(item.get("minimum_hops", 0))
        if item["answerable"]
        else True
    )

    return {
        "answerability_correct": answerability_correct,
        "answer_match": answer_match,
        "evidence_recall": round(evidence_recall, 4),
        "evidence_precision": round(evidence_precision, 4),
        "hop_requirement_met": hop_requirement_met,
        "task_success": bool(
            answerability_correct
            and answer_match
            and evidence_recall == 1.0
            and hop_requirement_met
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    benchmark = load_benchmark(args.dataset)
    gold = {item["id"]: item for item in benchmark["items"]}
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    if isinstance(predictions, dict):
        predictions = predictions.get("predictions", [])

    rows = []
    for prediction in predictions:
        item_id = prediction.get("id")
        if item_id not in gold:
            continue
        rows.append({
            "id": item_id,
            **evaluate_item(gold[item_id], prediction),
        })

    payload = {
        "schema": "aep-regulatory-evaluation-v1",
        "items": len(rows),
        "task_success_rate": (
            round(sum(row["task_success"] for row in rows) / len(rows), 4)
            if rows else None
        ),
        "answerability_accuracy": (
            round(sum(row["answerability_correct"] for row in rows) / len(rows), 4)
            if rows else None
        ),
        "answer_match_accuracy": (
            round(sum(row["answer_match"] for row in rows) / len(rows), 4)
            if rows else None
        ),
        "mean_evidence_recall": (
            round(sum(row["evidence_recall"] for row in rows) / len(rows), 4)
            if rows else None
        ),
        "mean_evidence_precision": (
            round(sum(row["evidence_precision"] for row in rows) / len(rows), 4)
            if rows else None
        ),
        "rows": rows,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
