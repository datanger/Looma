from __future__ import annotations

import argparse
import json
from pathlib import Path


METHODS = [
    "direct_sdk",
    "langgraph",
    "microsoft_agent_framework",
    "looma",
]


def balanced_latin_square(items: list[str]) -> list[list[str]]:
    """Return a balanced Latin square for an even number of conditions."""
    n = len(items)
    if n < 2 or n % 2:
        raise ValueError("balanced Latin square currently requires an even number of methods")

    first = []
    for index in range(n):
        if index % 2 == 0:
            position = index // 2
        else:
            position = n - 1 - index // 2
        first.append(items[position])

    rows = []
    for shift in range(n):
        rows.append([
            items[(items.index(value) + shift) % n]
            for value in first
        ])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--participants", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--tasks",
        default="adaptive_evidence,test_repair",
        help="Comma-separated task ids assigned alternately across sessions",
    )
    args = parser.parse_args()

    if args.participants < 4:
        parser.error("--participants must be >= 4 for the four-condition study")

    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]
    if len(tasks) < 2:
        parser.error("at least two task ids are required")

    square = balanced_latin_square(METHODS)
    assignments = []
    for participant_index in range(args.participants):
        order = square[participant_index % len(square)]
        task_offset = participant_index % len(tasks)
        sessions = [
            {
                "session": session_index + 1,
                "method": method,
                "task_id": tasks[(task_offset + session_index) % len(tasks)],
            }
            for session_index, method in enumerate(order)
        ]
        assignments.append({
            "participant_id": f"P{participant_index + 1:03d}",
            "sessions": sessions,
        })

    payload = {
        "schema": "aep-developer-study-assignments-v1",
        "design": "within-subject balanced Latin square",
        "methods": METHODS,
        "tasks": tasks,
        "participants": assignments,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
