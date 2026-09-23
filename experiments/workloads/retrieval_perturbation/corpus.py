"""Loading of public multi-hop QA corpora in their published shape.

Nothing in this module invents task content. It reads `questions.json` and
`chunks.json` exactly as published by the pinned A-RAG dataset revision, adapts
to the field names actually present, and records which shape it observed so the
run manifest can be audited.

Two evidence notions are supported, because the public files do not annotate
gold evidence uniformly:

* **exact**  — the question record carries gold evidence ids;
* **proxy**  — a chunk is gold evidence iff the normalized gold answer occurs in
  its normalized text. Reported as a proxy everywhere, never as ground truth.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


QUESTION_ID_KEYS = ("qid", "id", "_id", "question_id")
QUESTION_TEXT_KEYS = ("question", "query", "text")
GOLD_KEYS = ("answer", "gold_answer", "gold", "answers")
EVIDENCE_KEYS = (
    "supporting_chunk_ids",
    "supporting_facts",
    "supporting",
    "evidence",
    "chunk_ids",
    "paragraphs",
    "context_ids",
)
CHUNK_ID_KEYS = ("chunk_id", "id", "_id", "doc_id", "title")
CHUNK_TEXT_KEYS = ("text", "content", "chunk", "body", "paragraph")

_PUNCT = set(string.punctuation)
_ARTICLES = re.compile(r"\b(a|an|the)\b")


def normalize(text: Any) -> str:
    value = "" if text is None else str(text).lower()
    value = "".join(ch for ch in value if ch not in _PUNCT)
    value = _ARTICLES.sub(" ", value)
    return " ".join(value.split())


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def stable(value: str, seed: str = "") -> str:
    return hashlib.sha256(f"{seed}\0{value}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str


@dataclass(frozen=True)
class Question:
    qid: str
    question: str
    gold_answer: str
    gold_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class Corpus:
    dataset: str
    questions: tuple[Question, ...]
    chunks: tuple[Chunk, ...]
    shape: dict[str, Any]
    sources: dict[str, Any]

    def chunk_text(self, chunk_id: str) -> str | None:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk.text
        return None

    def question(self, qid: str) -> Question | None:
        for item in self.questions:
            if item.qid == qid:
                return item
        return None

    def chunks_containing(self, answer: str) -> tuple[str, ...]:
        needle = normalize(answer)
        if not needle:
            return ()
        return tuple(
            chunk.chunk_id
            for chunk in self.chunks
            if needle in normalize(chunk.text)
        )


def _first(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_as_text(item) for item in value.values())
    return "" if value is None else str(value)


def _evidence_ids(raw: Any) -> list[str]:
    """Best-effort extraction of gold evidence identifiers from a question record."""
    ids: list[str] = []
    if not isinstance(raw, (list, tuple)):
        return ids
    for item in raw:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            value = _first(item, ("chunk_id", "id", "_id", "doc_id", "title"))
            if isinstance(value, str):
                ids.append(value)
        elif isinstance(item, (list, tuple)) and item:
            head = item[0]
            if isinstance(head, str):
                ids.append(head)
    return ids


def _chunks_from_list(records: list[Any]) -> tuple[list[Chunk], str]:
    chunks: list[Chunk] = []
    for index, item in enumerate(records):
        if isinstance(item, dict):
            chunk_id = _first(item, CHUNK_ID_KEYS)
            text = _first(item, CHUNK_TEXT_KEYS)
            chunks.append(
                Chunk(
                    chunk_id=str(chunk_id) if chunk_id is not None else str(index),
                    text=_as_text(text),
                )
            )
        elif isinstance(item, str):
            chunks.append(Chunk(chunk_id=str(index), text=item))
    return chunks, "list"


def _chunks_from_mapping(records: dict[str, Any]) -> tuple[list[Chunk], str]:
    chunks: list[Chunk] = []
    for key, value in records.items():
        if isinstance(value, dict):
            text = _first(value, CHUNK_TEXT_KEYS)
            shape = "mapping[object]"
        else:
            text = value
            shape = "mapping[string]"
        chunks.append(Chunk(chunk_id=str(key), text=_as_text(text)))
    return chunks, shape


def load_corpus(dataset_dir: Path, dataset: str, *, limit: int | None = None) -> Corpus:
    questions_file = dataset_dir / "questions.json"
    chunks_file = dataset_dir / "chunks.json"
    for path in (questions_file, chunks_file):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing; run "
                "experiments.case_studies.arag_host_native.prepare_public_data first"
            )

    raw_questions = json.loads(questions_file.read_text(encoding="utf-8"))
    raw_chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
    if not isinstance(raw_questions, list):
        raise ValueError(f"{questions_file} must contain a JSON list")

    if isinstance(raw_chunks, dict):
        chunk_list, chunk_shape = _chunks_from_mapping(raw_chunks)
    elif isinstance(raw_chunks, list):
        chunk_list, chunk_shape = _chunks_from_list(raw_chunks)
    else:
        raise ValueError(f"{chunks_file} must contain a JSON list or object")

    known_ids = {chunk.chunk_id for chunk in chunk_list}
    questions: list[Question] = []
    for index, item in enumerate(raw_questions):
        if not isinstance(item, dict):
            continue
        qid = _first(item, QUESTION_ID_KEYS)
        gold = _first(item, GOLD_KEYS)
        evidence = tuple(
            candidate
            for candidate in _evidence_ids(_first(item, EVIDENCE_KEYS))
            if candidate in known_ids
        )
        questions.append(
            Question(
                qid=str(qid) if qid is not None else str(index),
                question=_as_text(_first(item, QUESTION_TEXT_KEYS)),
                gold_answer=_as_text(gold),
                gold_chunk_ids=evidence,
            )
        )
    if limit is not None:
        questions = questions[:limit]

    return Corpus(
        dataset=dataset,
        questions=tuple(questions),
        chunks=tuple(chunk_list),
        shape={
            "questions_container": "list",
            "chunks_container": chunk_shape,
            "chunk_id_key": "mapping-key"
            if chunk_shape.startswith("mapping")
            else next(
                (
                    key
                    for key in CHUNK_ID_KEYS
                    if any(
                        isinstance(item, dict) and key in item
                        for item in raw_chunks
                    )
                ),
                "index",
            ),
            "questions_with_exact_gold_evidence": sum(
                1 for item in questions if item.gold_chunk_ids
            ),
        },
        sources={
            "questions": {
                "path": str(questions_file),
                "sha256": digest(questions_file),
                "bytes": questions_file.stat().st_size,
            },
            "chunks": {
                "path": str(chunks_file),
                "sha256": digest(chunks_file),
                "bytes": chunks_file.stat().st_size,
            },
        },
    )