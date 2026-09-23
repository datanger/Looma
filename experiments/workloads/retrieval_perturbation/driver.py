"""Deterministic retrieval driver — the model stand-in for controlled mode.

`PAPER_PLAN.md` requires RQ2's controlled mode to hold model, tools, and budget
fixed. Offline and in CI there is no model, so every paradigm is driven by this
single deterministic policy.

Three honesty constraints are enforced here:

1. it never reads the gold answer, the gold evidence ids, or any scoring field —
   it sees the question and its own observations only;
2. it asks for the action it *wants* rather than for the action it is allowed to
   take; the session decides whether a route exists, which is exactly the
   quantity under measurement;
3. it cannot reason across hops, so controlled mode does not measure answer
   quality. It measures whether the evidence is still reachable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experiments.workloads.retrieval_perturbation.injectors import (
    ACTION_KEYWORD_SEARCH,
    ACTION_LIST_CHUNKS,
    ACTION_READ_CHUNK,
    ACTION_SEMANTIC_SEARCH,
    SEARCH_LIMIT,
)
from experiments.workloads.retrieval_perturbation.protocol import _terms

SEARCH_ACTIONS = (ACTION_SEMANTIC_SEARCH, ACTION_KEYWORD_SEARCH)


def sentences(text: str) -> list[str]:
    return [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]


@dataclass
class AdaptiveRetrievalDriver:
    question: str
    max_reads: int = 3
    min_support_terms: int = 2
    terms: list[str] = field(init=False)
    steps: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.terms = _terms(self.question)

    # ------------------------------------------------------------- trajectory

    def next_action(self, session) -> dict[str, Any] | None:
        """The next action the driver wants, or None when it is done."""
        search = self._ready_search(session)
        if search is None:
            return self._search_attempt(session)

        identifiers = self._identifiers(session, search)
        if identifiers is None:
            return {"action": ACTION_LIST_CHUNKS, "arguments": {}}
        if not identifiers:
            return None

        read_ids = session.read_ids()
        todo = [item for item in identifiers if item not in read_ids]
        if len(read_ids) < self.max_reads and todo:
            return {"action": ACTION_READ_CHUNK, "arguments": {"chunk_id": todo[0]}}
        return None

    def _ready_search(self, session) -> dict[str, Any] | None:
        for observation in reversed(session.observations):
            if observation["action"] in SEARCH_ACTIONS:
                if observation["result"].get("status") == "ready":
                    return observation["result"]
                return None
        return None

    def _search_attempt(self, session) -> dict[str, Any] | None:
        attempted = {observation["action"] for observation in session.observations}
        for action in SEARCH_ACTIONS:
            if action not in attempted:
                return {
                    "action": action,
                    "arguments": {"terms": self.terms, "top_k": SEARCH_LIMIT},
                }
        return None

    def _identifiers(self, session, search: dict[str, Any]) -> list[str] | None:
        """Usable chunk identifiers, or None when a catalog lookup is still needed."""
        direct = [str(item["chunk_id"]) for item in search.get("results", []) if "chunk_id" in item]
        if direct:
            return direct
        handles = [str(item["handle"]) for item in search.get("results", []) if "handle" in item]
        if not handles:
            return []
        resolved = session.resolve_handles()
        missing = [item for item in handles if item not in resolved]
        if missing:
            if any(o["action"] == ACTION_LIST_CHUNKS for o in session.observations):
                return []
            return None
        return [resolved[item] for item in handles if item in resolved]

    # ----------------------------------------------------------------- result

    def finish(self, session) -> dict[str, Any]:
        texts = session.read_texts()
        best: tuple[int, str, list[str]] | None = None
        for chunk_id, text in sorted(texts.items()):
            for sentence in sentences(text):
                hits = self._hits(sentence)
                if hits < min(self.min_support_terms, len(self.terms)):
                    continue
                candidate = (hits, sentence, [chunk_id])
                if best is None or candidate[0] > best[0] or (
                    candidate[0] == best[0] and candidate[1] < best[1]
                ):
                    best = candidate

        if best is None:
            return {
                "status": "insufficient",
                "answer": "",
                "cited_chunk_ids": [],
                "tool_path": list(session.tool_path),
                "confidence": 0,
            }

        threshold = min(self.min_support_terms, len(self.terms))
        cited = sorted(
            chunk_id
            for chunk_id, text in texts.items()
            if any(self._hits(sentence) >= threshold for sentence in sentences(text))
        )
        return {
            "status": "answered",
            "answer": best[1],
            "cited_chunk_ids": cited,
            "tool_path": list(session.tool_path),
            "confidence": min(100, best[0] * 25),
        }

    def _hits(self, sentence: str) -> int:
        lowered = sentence.lower()
        return sum(1 for term in self.terms if term in lowered)