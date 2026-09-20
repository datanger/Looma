from __future__ import annotations

import argparse
import json
from pathlib import Path

from looma import agent, step, workflow

from experiments.workloads.sotif_regulatory.dataset import (
    get_item,
    public_item,
)


AGENT_INPUT_SCHEMA = {
    "type": "object",
    "required": [
        "item",
        "dataset",
        "evidence_tool_module",
        "round",
        "previous_problems",
    ],
    "properties": {
        "item": {"type": "object"},
        "dataset": {"type": "string"},
        "evidence_tool_module": {"type": "string"},
        "round": {"type": "integer"},
        "previous_problems": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": False,
}

RESULT_SCHEMA = {
    "type": "object",
    "required": [
        "answerability",
        "answer",
        "evidence_ids",
        "reasoning_summary",
        "confidence",
    ],
    "properties": {
        "answerability": {
            "type": "string",
            "enum": ["answerable", "unanswerable"],
        },
        "answer": {"type": ["string", "null"]},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reasoning_summary": {"type": "string"},
        "confidence": {"type": "integer"},
    },
    "additionalProperties": False,
}


def validate_prediction(item: dict, result: dict) -> dict:
    problems = []
    catalog_ids = {
        evidence["evidence_id"] for evidence in item["evidence_catalog"]
    }
    cited = result.get("evidence_ids") or []
    unknown = sorted(set(cited) - catalog_ids)
    if unknown:
        problems.append(f"unknown evidence ids: {unknown}")

    if result.get("answerability") == "answerable":
        if not str(result.get("answer") or "").strip():
            problems.append("answerable result requires a non-empty answer")
        if len(set(cited)) < int(item.get("minimum_hops", 0)):
            problems.append("insufficient evidence-chain length")
    else:
        if str(result.get("answer") or "").strip():
            problems.append("unanswerable result must not invent an answer")

    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
    }


def write_prediction(path: str, item_id: str, result: dict, check: dict) -> dict:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": item_id,
        **result,
        "boundary_status": check["status"],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"path": str(target)}


@workflow
def analyze_item(
    dataset: str,
    item_id: str,
    output: str,
    max_rounds: int = 3,
):
    item = step(get_item, dataset, item_id)
    public = public_item(item)
    check = {"status": "revise", "problems": ["not started"]}
    result = None

    for round_index in range(max_rounds):
        result = agent(
            task=(
                "Analyze the regulatory/SOTIF-style question using only evidence "
                "that can be inspected through the supplied evidence tool. "
                "You control the evidence-reading trajectory and may follow multiple "
                "references before answering. Prefer the specified document version. "
                "If the corpus cannot support the requested conclusion, return "
                "answerability=unanswerable instead of inventing a rule. "
                "Do not launch another Coding Agent."
            ),
            input={
                "item": public,
                "dataset": dataset,
                "evidence_tool_module": (
                    "experiments.workloads.sotif_regulatory.evidence_tool"
                ),
                "round": round_index,
                "previous_problems": check["problems"],
            },
            input_schema=AGENT_INPUT_SCHEMA,
            output_schema=RESULT_SCHEMA,
        )
        check = step(validate_prediction, item, result)
        if check["status"] == "ready":
            break

    step(write_prediction, output, item_id, result or {}, check)
    return {
        "status": (
            "complete" if check["status"] == "ready"
            else "insufficient_evidence"
        ),
        "result": result,
        "validation": check,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    analyze_item(
        args.dataset,
        args.item,
        args.output,
        args.max_rounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
