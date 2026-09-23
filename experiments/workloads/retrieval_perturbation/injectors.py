"""Deterministic perturbations applied to a public corpus.

Every transform here is a pure function of `(public corpus, public question,
seed)`. No question text, gold answer, or paragraph is authored by this module:
chunks are only removed, re-keyed, or supplemented with *other public chunks*.

The perturbation is what the application discovers at run time; the route set it
declared before the run is what determines whether it can absorb it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from experiments.workloads.retrieval_perturbation.corpus import (
    Corpus,
    Question,
    normalize,
    stable,
)

ACTION_SEMANTIC_SEARCH = "semantic_search"
ACTION_KEYWORD_SEARCH = "keyword_search"
ACTION_READ_CHUNK = "read_chunk"
ACTION_LIST_CHUNKS = "list_chunks"
ACTION_KINDS = (
    ACTION_SEMANTIC_SEARCH,
    ACTION_KEYWORD_SEARCH,
    ACTION_READ_CHUNK,
    ACTION_LIST_CHUNKS,
)

#: Route set an application author would plausibly freeze after testing the
#: development split. It already covers the obvious fallback (keyword search).
DEV_ROUTE_SET = (
    ACTION_SEMANTIC_SEARCH,
    ACTION_KEYWORD_SEARCH,
    ACTION_READ_CHUNK,
)
#: Route set the evaluation split turns out to require.
WIDENED_ROUTE_SET = DEV_ROUTE_SET + (ACTION_LIST_CHUNKS,)
#: A Host Agent owns its own route set; a real Host would also use non-retrieval
#: actions, so the bound here is deliberately the whole retrieval vocabulary.
HOST_NATIVE_ROUTE_SET = ACTION_KINDS

BASELINE = "baseline"
PRIMARY_TOOL_UNAVAILABLE = "primary_tool_unavailable"
SOURCE_ID_RENAMED = "source_id_renamed"
SNIPPET_ONLY = "snippet_only"
EVIDENCE_WITHHELD = "evidence_withheld"
DISTRACTOR_CHUNK = "distractor_chunk"

PERTURBATIONS = (
    BASELINE,
    PRIMARY_TOOL_UNAVAILABLE,
    SOURCE_ID_RENAMED,
    SNIPPET_ONLY,
    EVIDENCE_WITHHELD,
    DISTRACTOR_CHUNK,
)

#: Perturbations an application author could have tested before freezing routes.
DEV_PERTURBATIONS = (BASELINE, PRIMARY_TOOL_UNAVAILABLE)
#: Perturbations only discovered in the held-out batch.
EVAL_PERTURBATIONS = (
    SOURCE_ID_RENAMED,
    SNIPPET_ONLY,
    EVIDENCE_WITHHELD,
    DISTRACTOR_CHUNK,
)

WITHHELD_KEEP_PERCENT = 60
SEARCH_LIMIT = 5


def split_of(perturbation: str) -> str:
    if perturbation not in PERTURBATIONS:
        raise ValueError(f"unknown perturbation: {perturbation!r}")
    return "dev" if perturbation in DEV_PERTURBATIONS else "eval"


def keeps_chunk(seed: str, dataset: str, chunk_id: str) -> bool:
    bucket = int(
        hashlib.sha256(f"{seed}\0{dataset}\0{chunk_id}".encode("utf-8")).hexdigest()[:8],
        16,
    ) % 100
    return bucket < WITHHELD_KEEP_PERCENT


@dataclass
class Environment:
    """The perturbed retrieval environment one task instance runs against."""

    dataset: str
    qid: str
    perturbation: str
    seed: str
    question: str
    gold_answer: str
    chunks: dict[str, str]
    origin_of: dict[str, str]
    available_actions: tuple[str, ...]
    hides_ids: bool
    exact_gold_ids: bool
    gold_evidence_ids: tuple[str, ...]
    evidence_present: bool
    manifest: dict[str, Any] = field(default_factory=dict)

    def resolve(self, visible_id: str) -> str | None:
        return self.origin_of.get(visible_id)

    def chunks_sha(self) -> str:
        payload = "\n".join(
            f"{visible_id}\0{text}" for visible_id, text in sorted(self.chunks.items())
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "handle": handle(visible_id),
                "chars": len(text),
                "visible_id": visible_id,
            }
            for visible_id, text in sorted(self.chunks.items())
        ]

    def public(self) -> dict[str, Any]:
        """Instance description safe to place inside an `agent()` boundary.

        It contains no gold answer and no gold evidence id, so a Host Agent
        cannot read the answer off its own boundary input.
        """
        return {
            "dataset": self.dataset,
            "qid": self.qid,
            "perturbation": self.perturbation,
            "question": self.question,
            "chunk_count": len(self.chunks),
            "hides_ids": self.hides_ids,
            "declared_environment_actions": list(self.available_actions),
        }

    def payload(self) -> dict[str, Any]:
        """Serializable, **gold-free** view handed to a paradigm process.

        `origin_of` and every gold field are deliberately absent: this payload is
        read by the Host in AEP mode, so anything in it is potentially visible to
        the agent under measurement.
        """
        return {
            "schema": "aep-retrieval-instance-v1",
            "dataset": self.dataset,
            "qid": self.qid,
            "perturbation": self.perturbation,
            "seed": self.seed,
            "question": self.question,
            "chunks": dict(self.chunks),
            "available_actions": list(self.available_actions),
            "hides_ids": self.hides_ids,
            "manifest": dict(self.manifest),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Environment":
        """Rebuild the environment a paradigm process is allowed to see.

        Gold fields are empty by construction; scoring happens in the runner,
        which keeps its own instance built from the public corpus.
        """
        chunks = {str(key): str(value) for key, value in payload["chunks"].items()}
        return cls(
            dataset=str(payload["dataset"]),
            qid=str(payload["qid"]),
            perturbation=str(payload["perturbation"]),
            seed=str(payload.get("seed", "")),
            question=str(payload["question"]),
            gold_answer="",
            chunks=chunks,
            origin_of={chunk_id: chunk_id for chunk_id in chunks},
            available_actions=tuple(payload["available_actions"]),
            hides_ids=bool(payload["hides_ids"]),
            exact_gold_ids=False,
            gold_evidence_ids=(),
            evidence_present=False,
            manifest=dict(payload.get("manifest") or {}),
        )


def handle(visible_id: str) -> str:
    return "h" + stable(visible_id, "handle")[:8]


def _renamed(dataset: str, seed: str, chunk_id: str) -> str:
    return "c" + stable(f"{dataset}\0{chunk_id}", seed)[:10]


def build_environment(
    corpus: Corpus,
    question: Question,
    perturbation: str,
    *,
    seed: str = "aep-paper-v1",
) -> Environment:
    if perturbation not in PERTURBATIONS:
        raise ValueError(f"unknown perturbation: {perturbation!r}")

    base: dict[str, str] = {chunk.chunk_id: chunk.text for chunk in corpus.chunks}
    visible: dict[str, str]
    origin_of: dict[str, str]
    available = list(ACTION_KINDS)
    notes: list[str] = []

    if perturbation == EVIDENCE_WITHHELD:
        kept = {
            chunk_id: text
            for chunk_id, text in base.items()
            if keeps_chunk(seed, corpus.dataset, chunk_id)
        }
        notes.append(
            f"corpus truncated to {len(kept)}/{len(base)} chunks "
            f"({WITHHELD_KEEP_PERCENT}% deterministic subset)"
        )
    else:
        kept = dict(base)

    if perturbation == PRIMARY_TOOL_UNAVAILABLE:
        available = [item for item in available if item != ACTION_SEMANTIC_SEARCH]
        notes.append("semantic_search withdrawn from the environment tool surface")

    if perturbation == DISTRACTOR_CHUNK:
        ordered = sorted(base)
        if ordered:
            pick = int(stable(f"{corpus.dataset}\0{question.qid}", seed)[:8], 16) % len(ordered)
            target = ordered[pick]
            if target in question.gold_chunk_ids and len(ordered) > 1:
                target = ordered[(pick + 1) % len(ordered)]
            kept.setdefault(target, base[target])
            notes.append(
                f"one further public chunk attached as a competing source: {target!r}"
            )

    hides_ids = perturbation in (SOURCE_ID_RENAMED, SNIPPET_ONLY)
    if hides_ids:
        visible = {}
        origin_of = {}
        for chunk_id, text in sorted(kept.items()):
            renamed = _renamed(corpus.dataset, seed, chunk_id)
            visible[renamed] = text
            origin_of[renamed] = chunk_id
        notes.append("chunk identifiers remapped; search returns opaque handles")
    else:
        visible = dict(kept)
        origin_of = {chunk_id: chunk_id for chunk_id in kept}

    gold, exact = gold_evidence(corpus, question, visible, origin_of)

    return Environment(
        dataset=corpus.dataset,
        qid=question.qid,
        perturbation=perturbation,
        seed=seed,
        question=question.question,
        gold_answer=question.gold_answer,
        chunks=visible,
        origin_of=origin_of,
        available_actions=tuple(available),
        hides_ids=hides_ids,
        exact_gold_ids=exact,
        gold_evidence_ids=gold,
        evidence_present=bool(gold),
        manifest={
            "perturbation": perturbation,
            "split": split_of(perturbation),
            "seed": seed,
            "chunks_before": len(base),
            "chunks_after": len(visible),
            "hides_ids": hides_ids,
            "available_actions": available,
            "evidence_mode": "exact" if exact else "proxy",
            "notes": notes,
        },
    )


def gold_evidence(
    corpus: Corpus,
    question: Question,
    chunks: dict[str, str],
    origin_of: dict[str, str],
) -> tuple[tuple[str, ...], bool]:
    """Visible gold-evidence ids for the perturbed view of the corpus.

    Returns `(ids, exact)`. `exact` is True only when the public question record
    itself carried gold evidence ids, in which case the match is made on the
    original ids through `origin_of`.
    """
    if question.gold_chunk_ids:
        originals = set(question.gold_chunk_ids)
        return (
            tuple(
                visible_id
                for visible_id, original in sorted(origin_of.items())
                if original in originals
            ),
            True,
        )
    needle = normalize(question.gold_answer)
    if not needle:
        return ((), False)
    return (
        tuple(
            visible_id
            for visible_id, text in sorted(chunks.items())
            if needle in normalize(text)
        ),
        False,
    )


def build_environments(
    corpus: Corpus,
    perturbation: str,
    *,
    seed: str = "aep-paper-v1",
    limit: int | None = None,
) -> list[Environment]:
    questions = corpus.questions[:limit] if limit is not None else corpus.questions
    return [
        build_environment(corpus, question, perturbation, seed=seed)
        for question in questions
    ]


def instance_id(environment: Environment) -> str:
    return f"{environment.dataset}:{environment.qid}:{environment.perturbation}"


def corpus_fingerprint(environments: list[Environment]) -> str:
    payload = "\n".join(
        f"{instance_id(environment)}\0{environment.chunks_sha()}"
        for environment in environments
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()