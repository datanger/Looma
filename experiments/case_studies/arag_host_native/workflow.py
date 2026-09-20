from __future__ import annotations

import argparse

from looma import agent, step, workflow

from experiments.case_studies.arag_host_native.validate_answer import (
    validate_answer,
)


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


@workflow
def answer_question(
    question: str,
    config: str,
    session_file: str,
    max_rounds: int = 3,
):
    check = {
        "status": "revise",
        "problems": ["not started"],
    }
    result = None

    for round_index in range(max_rounds):
        result = agent(
            task=(
                "Answer the question using the unmodified A-RAG retrieval tools "
                "through experiments/case_studies/arag_host_native/bridge.py. "
                "Use the current Host's native terminal/tool capability. "
                "Do not launch another Coding Agent or an internal LLM client. "
                "Choose keyword_search, semantic_search, and read_chunk autonomously. "
                "Search snippets are discovery evidence only; read every chunk that "
                "supports the final answer. Repair previous validation problems."
            ),
            input={
                "question": question,
                "round": round_index,
                "config": config,
                "session_file": session_file,
                "previous_validation_problems": check["problems"],
            },
            output_schema=ANSWER_SCHEMA,
        )
        check = step(
            validate_answer,
            result,
            session_file,
        )
        if check["status"] == "ready":
            break

    return {
        "status": (
            "complete"
            if check["status"] == "ready"
            else "insufficient_evidence"
        ),
        "result": result,
        "validation": check,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--session",
        default=".looma/arag-host-native-session.json",
    )
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    answer_question(
        args.question,
        args.config,
        args.session,
        args.max_rounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
