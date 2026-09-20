from __future__ import annotations

import json
from pathlib import Path


def validate_answer(result: dict, session_file: str) -> dict:
    problems: list[str] = []
    answer = result.get("answer")
    cited = result.get("cited_chunk_ids")

    if not isinstance(answer, str) or not answer.strip():
        problems.append("answer is empty")
    if not isinstance(cited, list) or not cited:
        problems.append("cited_chunk_ids must contain at least one chunk")
        cited = []

    session = Path(session_file)
    if not session.exists():
        problems.append("retrieval session file does not exist")
        read_ids: set[str] = set()
    else:
        data = json.loads(session.read_text(encoding="utf-8"))
        read_ids = {
            str(item) for item in data.get("chunks_read_ids", [])
        }

    unread = sorted({str(item) for item in cited} - read_ids)
    if unread:
        problems.append(
            "answer cites chunks that were not actually read: "
            + ", ".join(unread)
        )

    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "read_chunk_ids": sorted(read_ids),
    }
