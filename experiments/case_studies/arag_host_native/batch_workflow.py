from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from looma import agent, step, workflow

from experiments.case_studies.arag_host_native.validate_answer import (
    validate_answer,
)


AGENT_INPUT_SCHEMA = {
    "type": "object",
    "required": [
        "qid",
        "question",
        "round",
        "config",
        "session_file",
        "bridge_module",
        "previous_validation_problems",
    ],
    "properties": {
        "qid": {"type": "string"},
        "question": {"type": "string"},
        "round": {"type": "integer"},
        "config": {"type": "string"},
        "session_file": {"type": "string"},
        "bridge_module": {"type": "string"},
        "previous_validation_problems": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": False,
}


ANSWER_SCHEMA = {
    "type": "object",
    "required": [
        "answer",
        "cited_chunk_ids",
        "tool_path",
        "confidence",
    ],
    "properties": {
        "answer": {"type": "string"},
        "cited_chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tool_path": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "integer"},
    },
    "additionalProperties": False,
}


def load_questions(path: str, limit: int | None) -> list[dict[str, Any]]:
    questions = json.loads(Path(path).read_text(encoding="utf-8"))
    return questions[:limit] if limit is not None else questions


def session_metrics(path: str) -> dict[str, Any]:
    session = Path(path)
    if not session.exists():
        return {
            "total_retrieved_tokens": 0,
            "retrieval_logs": [],
            "chunks_read_count": 0,
            "chunks_read_ids": [],
        }
    data = json.loads(session.read_text(encoding="utf-8"))
    return {
        "total_retrieved_tokens": int(
            data.get("total_retrieved_tokens", 0)
        ),
        "retrieval_logs": list(data.get("retrieval_logs", [])),
        "chunks_read_count": int(
            data.get(
                "chunks_read_count",
                len(data.get("chunks_read_ids", [])),
            )
        ),
        "chunks_read_ids": list(data.get("chunks_read_ids", [])),
    }


def write_predictions(path: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False) + "\n"
            )
    return {"path": str(target), "rows": len(rows)}


@workflow
def run_batch(
    questions_file: str,
    config: str,
    output: str,
    sessions_dir: str,
    limit: int | None = None,
    max_rounds: int = 3,
):
    questions = step(load_questions, questions_file, limit)
    predictions: list[dict[str, Any]] = []

    for index, item in enumerate(questions):
        qid = item.get("qid") or item.get("id") or str(index)
        question = item.get("question", "")
        gold_answer = item.get("answer", item.get("gold_answer", ""))
        session_file = str(
            Path(sessions_dir) / f"{qid}.json"
        )

        check = {
            "status": "revise",
            "problems": ["not started"],
        }
        result = None
        host_rounds = 0

        for round_index in range(max_rounds):
            host_rounds += 1
            result = agent(
                task=(
                    "Solve this multi-hop QA item by controlling A-RAG's "
                    "unmodified retrieval tools through "
                    "experiments/case_studies/arag_host_native/bridge.py. "
                    "Use the current Host's native terminal/tool capability. "
                    "Do not launch another Coding Agent and do not instantiate "
                    "A-RAG BaseAgent or LLMClient. Choose keyword_search, "
                    "semantic_search, and read_chunk autonomously. Search "
                    "snippets are discovery evidence only; read all chunks "
                    "used for the final answer. Return a concise answer."
                ),
                input={
                    "qid": qid,
                    "question": question,
                    "round": round_index,
                    "config": config,
                    "session_file": session_file,
                    "bridge_module": (
                        "experiments.case_studies."
                        "arag_host_native.bridge"
                    ),
                    "previous_validation_problems": check["problems"],
                },
                input_schema=AGENT_INPUT_SCHEMA,
                output_schema=ANSWER_SCHEMA,
            )
            check = step(
                validate_answer,
                result,
                session_file,
            )
            if check["status"] == "ready":
                break

        metrics = step(session_metrics, session_file)
        accepted = check["status"] == "ready"
        predictions.append(
            {
                "qid": qid,
                "question": question,
                "gold_answer": gold_answer,
                "pred_answer": (
                    result.get("answer", "")
                    if result is not None
                    else ""
                ),
                "status": (
                    "answered"
                    if accepted
                    else "insufficient_evidence"
                ),
                "host_rounds": host_rounds,
                "tool_path": (
                    result.get("tool_path", [])
                    if result is not None
                    else []
                ),
                "cited_chunk_ids": (
                    result.get("cited_chunk_ids", [])
                    if result is not None
                    else []
                ),
                "confidence": (
                    result.get("confidence")
                    if result is not None
                    else None
                ),
                **metrics,
            }
        )

    step(write_predictions, output, predictions)
    return {
        "status": "complete",
        "questions": len(predictions),
        "output": output,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--sessions-dir",
        default=".looma/arag-host-native-sessions",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    run_batch(
        args.questions,
        args.config,
        args.output,
        args.sessions_dir,
        args.limit,
        args.max_rounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
