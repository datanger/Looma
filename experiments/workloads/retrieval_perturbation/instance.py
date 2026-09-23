"""Instance construction: public corpus + public question + perturbation.

The runner builds instances in-process and writes a **gold-free** payload per
instance. Paradigm processes only ever read that payload, so a Host Agent in AEP
mode cannot obtain the expected answer from its own inputs. Scoring stays in the
runner, which keeps the gold-bearing `Environment` it built from the corpus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from experiments.workloads.retrieval_perturbation.corpus import (
    Corpus,
    Question,
    load_corpus,
)
from experiments.workloads.retrieval_perturbation.injectors import (
    PERTURBATIONS,
    Environment,
    build_environment,
    split_of,
)

DEFAULT_SEED = "aep-paper-v1"


@dataclass(frozen=True)
class Instance:
    corpus: Corpus
    question: Question
    environment: Environment

    @property
    def instance_id(self) -> str:
        return (
            f"{self.environment.dataset}:{self.environment.qid}:"
            f"{self.environment.perturbation}"
        )

    @property
    def split(self) -> str:
        return split_of(self.environment.perturbation)


def load_instance(
    data_root: Path,
    dataset: str,
    qid: str,
    perturbation: str,
    *,
    seed: str = DEFAULT_SEED,
) -> Instance:
    corpus = load_corpus(data_root / dataset, dataset)
    question = corpus.question(qid)
    if question is None:
        raise KeyError(f"question {qid!r} is not in {dataset}")
    return Instance(
        corpus=corpus,
        question=question,
        environment=build_environment(corpus, question, perturbation, seed=seed),
    )


def select_instances(
    data_root: Path,
    dataset: str,
    *,
    perturbations: tuple[str, ...] = PERTURBATIONS,
    limit: int | None = None,
    seed: str = DEFAULT_SEED,
) -> list[Instance]:
    """All (question, perturbation) instances of one dataset, in a stable order."""
    corpus = load_corpus(data_root / dataset, dataset)
    questions = corpus.questions[:limit] if limit is not None else corpus.questions
    instances: list[Instance] = []
    for perturbation in perturbations:
        for question in questions:
            instances.append(
                Instance(
                    corpus=corpus,
                    question=question,
                    environment=build_environment(
                        corpus, question, perturbation, seed=seed
                    ),
                )
            )
    return instances


def write_payload(instance: Instance, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = instance.environment.payload()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"path": str(path), "bytes": path.stat().st_size}


def read_payload(path: Path) -> Environment:
    return Environment.from_payload(json.loads(path.read_text(encoding="utf-8")))