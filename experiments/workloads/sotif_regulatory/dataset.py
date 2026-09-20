from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from looma.schema import validate_json_schema


HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "benchmark_schema.json"


def load_benchmark(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = validate_json_schema(value, schema)
    if errors:
        raise ValueError(
            "benchmark schema validation failed: "
            + json.dumps(errors, ensure_ascii=False)
        )

    ids = [item["id"] for item in value["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark item ids must be unique")

    for item in value["items"]:
        evidence_ids = {
            evidence["evidence_id"] for evidence in item["evidence_catalog"]
        }
        unknown = sorted(set(item["gold_evidence_ids"]) - evidence_ids)
        if unknown:
            raise ValueError(
                f"{item['id']}: unknown gold evidence ids: {unknown}"
            )
        if item["answerable"] and not item.get("gold_answer"):
            raise ValueError(
                f"{item['id']}: answerable item requires gold_answer"
            )
        if not item["answerable"] and item.get("gold_answer") not in (None, ""):
            raise ValueError(
                f"{item['id']}: unanswerable item must not define gold_answer"
            )
    return value


def get_item(path: str | Path, item_id: str) -> dict[str, Any]:
    benchmark = load_benchmark(path)
    for item in benchmark["items"]:
        if item["id"] == item_id:
            return item
    raise KeyError(f"unknown benchmark item: {item_id}")


def public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "question": item["question"],
        "scenario": item.get("scenario", ""),
        "task_type": item["task_type"],
        "minimum_hops": item.get("minimum_hops", 0),
        "evidence_catalog": [
            {
                key: value
                for key, value in evidence.items()
                if key not in {"text"}
            }
            for evidence in item["evidence_catalog"]
        ],
    }
