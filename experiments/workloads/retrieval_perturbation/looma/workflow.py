"""AEP / Looma on the public retrieval-perturbation suite.

The application declares **no retrieval route at all**. It declares a semantic
task boundary ("answer, or say the evidence is insufficient"), a Result Contract,
and a program-owned acceptance gate. Which of the four retrieval tools the Host
performs, in which order, and how it reacts when the environment withdraws a tool
or re-keys a corpus, is entirely the Host's business.

Consequence, and the point of the comparison: this file is byte-identical for the
development and the held-out batches. Widening the reachable action set is a
Host-side act that costs the application zero SLOC.
"""

from __future__ import annotations

import json
from pathlib import Path

from looma import agent, step, workflow

from experiments.workloads.retrieval_perturbation.injectors import split_of
from experiments.workloads.retrieval_perturbation.protocol import (
    STATUS_COMPLETE,
    STATUS_INSUFFICIENT,
    read_session,
    validate_result,
    write_report,
)

IMPLEMENTATION = "looma"
MAX_ROUNDS = 2

TASK = (
    "Answer the retrieval item with non-fabricated evidence.\n"
    "The corpus for this item is described by `instance_file`; retrieve through the "
    "tool surface the environment offers you. Use your own native tools and terminal. "
    "Do not launch another Coding Agent and do not call a model API directly.\n"
    "The environment may have changed since the task was written: a tool may be "
    "absent, chunk identifiers may not be the ones you expect, and the corpus may not "
    "contain the evidence the question needs. Discover what is actually reachable "
    "instead of assuming a fixed pipeline, and reorder or revisit your retrieval path "
    "freely.\n"
    "Cite only chunks you actually read. If the evidence the question needs cannot be "
    "obtained, return status 'insufficient' with an empty answer instead of guessing."
)

INPUT_SCHEMA = {
    "type": "object",
    "required": [
        "run_id",
        "instance_file",
        "session_file",
        "round",
        "question",
        "perturbation",
        "previous_validation_problems",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "instance_file": {"type": "string"},
        "session_file": {"type": "string"},
        "round": {"type": "integer"},
        "question": {"type": "string"},
        "perturbation": {"type": "string"},
        "chunk_count": {"type": "integer"},
        "hides_ids": {"type": "boolean"},
        "previous_validation_problems": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

RESULT_SCHEMA = {
    "type": "object",
    "required": ["status", "answer", "cited_chunk_ids", "tool_path", "confidence"],
    "properties": {
        "status": {"type": "string", "enum": ["answered", "insufficient"]},
        "answer": {"type": "string"},
        "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
        "tool_path": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "integer"},
    },
    "additionalProperties": False,
}


def read_instance(instance_file: str) -> dict:
    """JSON-compatible, gold-free payload for one public task instance."""
    payload = json.loads(Path(instance_file).read_text(encoding="utf-8"))
    return {
        "run_id": f"{payload['dataset']}:{payload['qid']}:{payload['perturbation']}",
        "dataset": str(payload["dataset"]),
        "qid": str(payload["qid"]),
        "perturbation": str(payload["perturbation"]),
        "question": str(payload["question"]),
        "chunk_count": len(payload["chunks"]),
        "hides_ids": bool(payload["hides_ids"]),
    }


def read_session_or_empty(session_file: str) -> dict:
    path = Path(session_file)
    if not path.exists():
        return {}
    return read_session(path)


@workflow
def answer_with_retrieval(
    instance_file: str,
    output: str,
    session_file: str,
    max_rounds: int = MAX_ROUNDS,
) -> dict:
    instance = step(read_instance, instance_file)

    check = {"status": "revise", "problems": ["not started"]}
    result = None
    rounds = 0
    for round_index in range(max_rounds):
        rounds += 1
        result = agent(
            task=TASK,
            input={
                "run_id": instance["run_id"],
                "instance_file": instance_file,
                "session_file": session_file,
                "round": round_index,
                "question": instance["question"],
                "perturbation": instance["perturbation"],
                "chunk_count": instance["chunk_count"],
                "hides_ids": instance["hides_ids"],
                "previous_validation_problems": check["problems"],
            },
            input_schema=INPUT_SCHEMA,
            output_schema=RESULT_SCHEMA,
        )
        check = step(validate_result, result, session_file)
        if check["status"] == "ready":
            break

    session = step(read_session_or_empty, session_file)
    if check["status"] != "ready":
        status = STATUS_INSUFFICIENT
    elif result is not None and result.get("status") == "answered":
        status = STATUS_COMPLETE
    else:
        status = STATUS_INSUFFICIENT

    report = {
        "instance_id": instance["run_id"],
        "implementation": IMPLEMENTATION,
        "routes_mode": "host_native",
        "split": split_of(instance["perturbation"]),
        "status": status,
        "rounds": rounds,
        # The application declares no route. The Host owns the reachable action
        # set, which is why this list is empty in both batches.
        "declared_actions": [],
        "environment_actions": session.get("environment_actions", []),
        "host_declared_actions": session.get("declared_actions", []),
        "actions_used": session.get("actions_used", 0),
        "tool_path": session.get("tool_path", []),
        "route_gaps": [],
        "result": result,
        "validation": check,
        "error": None,
    }
    step(write_report, output, report)
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()
    report = answer_with_retrieval(
        args.instance, args.output, args.session, args.max_rounds
    )
    print(f"RETRIEVAL_RESULT implementation={IMPLEMENTATION} status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())