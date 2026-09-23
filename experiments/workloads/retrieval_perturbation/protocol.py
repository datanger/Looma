"""Shared retrieval tool surface, boundary gate, and experiment-side scoring.

The single variable of the comparison is *which actions the application's
orchestration can reach*. Every paradigm talks to the perturbed environment
through the same `RetrievalSession`, constructed with the action set the
application declared. When the deterministic driver wants an action the
application never declared a route for, the session raises `RouteMissing` and the
run is recorded as a dead end. That is the measured quantity, not a bug.

Two distinct failure modes are kept apart on purpose:

* **environment unavailable** — the tool is not offered; the driver receives an
  `unavailable` observation and may adapt. This is semantics.
* **route missing** — the application's orchestration has no path to the action.
  This is structure, and it is what a widening edit would have to fix.

Scoring never crosses the `agent()` boundary. `validate_result` sees only facts
derivable from the persisted session; `score_result` is experiment-side and is
the only place the public gold answer is read.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from experiments.workloads.retrieval_perturbation.corpus import normalize
from experiments.workloads.retrieval_perturbation.injectors import (
    ACTION_KEYWORD_SEARCH,
    ACTION_LIST_CHUNKS,
    ACTION_READ_CHUNK,
    ACTION_SEMANTIC_SEARCH,
    SEARCH_LIMIT,
    Environment,
    handle,
)

MAX_ACTIONS_PER_ROUND = 12
MAX_ROUNDS = 2

STATUS_COMPLETE = "complete"
STATUS_INSUFFICIENT = "insufficient_evidence"
STATUS_DEAD_END = "dead_end"
STATUS_BUDGET = "budget_exceeded"
STATUS_ERROR = "error"

OUTCOME_ANSWERED_CORRECT = "answered_correct"
OUTCOME_ANSWERED_WRONG = "answered_wrong"
OUTCOME_REFUSED = "refused"

SNIPPET_CHARS = 160


class HarnessError(RuntimeError):
    pass


class RouteMissing(HarnessError):
    """The application declared no route for an action the driver asked for."""

    def __init__(self, action: str, declared: tuple[str, ...]):
        super().__init__(
            f"no declared route for action {action!r} "
            f"(declared actions: {', '.join(declared) or 'none'})"
        )
        self.action = action
        self.declared = list(declared)

    def as_dict(self) -> dict[str, Any]:
        return {"action": self.action, "declared_actions": self.declared}


class ActionBudgetExceeded(HarnessError):
    def __init__(self, used: int, limit: int):
        super().__init__(f"action budget exceeded: {used} > {limit}")
        self.used = used
        self.limit = limit


def _terms(text: str) -> list[str]:
    stop = {
        "the", "a", "an", "of", "in", "on", "at", "to", "and", "or", "is", "are",
        "was", "were", "who", "what", "which", "when", "where", "why", "how", "did",
        "does", "do", "for", "by", "with", "that", "this", "it", "its", "as", "from",
    }
    words = [word for word in normalize(text).split() if word not in stop]
    return [word for word in words if len(word) > 1]


def _snippet(text: str, terms: list[str]) -> str:
    sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    if not sentences:
        return text[:SNIPPET_CHARS]
    best = max(
        sentences,
        key=lambda sentence: (
            sum(term in normalize(sentence) for term in terms),
            -len(sentence),
        ),
    )
    return best[:SNIPPET_CHARS]


def _rank(chunks: dict[str, str], terms: list[str]) -> list[tuple[int, str]]:
    scored: list[tuple[int, str]] = []
    for chunk_id, text in sorted(chunks.items()):
        haystack = normalize(text)
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            scored.append((hits, chunk_id))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return scored


@dataclass
class RetrievalSession:
    """One application's view of one perturbed task instance."""

    environment: Environment
    declared_actions: tuple[str, ...]
    max_actions: int = MAX_ACTIONS_PER_ROUND
    observations: list[dict[str, Any]] = field(default_factory=list)
    tool_path: list[str] = field(default_factory=list)
    route_gaps: list[dict[str, Any]] = field(default_factory=list)
    retrieval_logs: list[dict[str, Any]] = field(default_factory=list)

    # ---------------------------------------------------------------- execution

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        action = str(request.get("action"))
        if action not in self.declared_actions:
            gap = RouteMissing(action, tuple(self.declared_actions))
            self.route_gaps.append(gap.as_dict())
            self.tool_path.append(f"unsupported:{action}")
            raise gap
        if len(self.observations) >= self.max_actions:
            raise ActionBudgetExceeded(len(self.observations), self.max_actions)

        if action not in self.environment.available_actions:
            observation = self._noted(
                action,
                {
                    "status": "unavailable",
                    "action": action,
                    "reason": "the environment does not offer this tool",
                    "environment_actions": list(self.environment.available_actions),
                },
            )
            return observation

        arguments = dict(request.get("arguments") or {})
        if action in (ACTION_SEMANTIC_SEARCH, ACTION_KEYWORD_SEARCH):
            observation = self._search(action, arguments)
        elif action == ACTION_READ_CHUNK:
            observation = self._read(arguments)
        elif action == ACTION_LIST_CHUNKS:
            observation = self._catalog()
        else:  # pragma: no cover - guarded by the declared-action check
            raise HarnessError(f"unknown action: {action!r}")
        return observation

    def _noted(self, action: str, result: dict[str, Any]) -> dict[str, Any]:
        self.tool_path.append(f"{action}:{result['status']}")
        observation = {"action": action, "result": result, "at": len(self.observations)}
        self.observations.append(observation)
        return observation

    def record_unsupported(self, error: "RouteMissing") -> dict[str, Any]:
        """Turn a structural gap into an observation the driver can react to.

        A workflow that cannot execute an action still has to reach a decision
        from the evidence it can reach. The gap is recorded so the harness can
        attribute the outcome to the declared route set, and the driver learns
        not to ask again.
        """
        return self._noted(
            error.action,
            {
                "status": "unsupported",
                "action": error.action,
                "reason": "the application declared no route for this action",
                "declared_actions": list(error.declared),
            },
        )

    def _search(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        terms = _terms(" ".join(str(item) for item in arguments.get("terms", [])))
        ranked = _rank(self.environment.chunks, terms)[: int(arguments.get("top_k", SEARCH_LIMIT))]
        results = []
        for _, chunk_id in ranked:
            text = self.environment.chunks[chunk_id]
            entry = {"snippet": _snippet(text, terms)}
            if self.environment.hides_ids:
                entry["handle"] = handle(chunk_id)
            else:
                entry["chunk_id"] = chunk_id
            results.append(entry)
        self.retrieval_logs.append({"tool": action, "terms": terms, "hits": len(results)})
        return self._noted(
            action,
            {
                "status": "ready",
                "results": results,
                "chunks_found": len(results),
                "identifiers": "handle" if self.environment.hides_ids else "chunk_id",
            },
        )

    def _read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        chunk_id = str(arguments.get("chunk_id", ""))
        text = self.environment.chunks.get(chunk_id)
        if text is None:
            return self._noted(
                ACTION_READ_CHUNK,
                {
                    "status": "not_found",
                    "chunk_id": chunk_id,
                    "reason": "no such chunk identifier in this environment",
                },
            )
        self.retrieval_logs.append({"tool": ACTION_READ_CHUNK, "chunk_id": chunk_id, "chars": len(text)})
        return self._noted(
            ACTION_READ_CHUNK,
            {"status": "ready", "chunk_id": chunk_id, "text": text, "chars": len(text)},
        )

    def _catalog(self) -> dict[str, Any]:
        entries = [
            {"handle": handle(chunk_id), "chunk_id": chunk_id, "chars": len(text)}
            for chunk_id, text in sorted(self.environment.chunks.items())
        ]
        self.retrieval_logs.append({"tool": ACTION_LIST_CHUNKS, "entries": len(entries)})
        return self._noted(
            ACTION_LIST_CHUNKS,
            {"status": "ready", "catalog": entries, "chunks_found": len(entries)},
        )

    # ----------------------------------------------------------------- reading

    def read_ids(self) -> set[str]:
        return {
            str(observation["result"]["chunk_id"])
            for observation in self.observations
            if observation["action"] == ACTION_READ_CHUNK
            and observation["result"].get("status") == "ready"
        }

    def read_texts(self) -> dict[str, str]:
        return {
            str(observation["result"]["chunk_id"]): str(observation["result"]["text"])
            for observation in self.observations
            if observation["action"] == ACTION_READ_CHUNK
            and observation["result"].get("status") == "ready"
        }

    def handles_seen(self) -> list[str]:
        seen: list[str] = []
        for observation in self.observations:
            if observation["action"] not in (ACTION_SEMANTIC_SEARCH, ACTION_KEYWORD_SEARCH):
                continue
            for item in observation["result"].get("results", []):
                if "handle" in item:
                    seen.append(str(item["handle"]))
        return seen

    def resolve_handles(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for observation in self.observations:
            if observation["action"] != ACTION_LIST_CHUNKS:
                continue
            for entry in observation["result"].get("catalog", []):
                mapping[str(entry["handle"])] = str(entry["chunk_id"])
        return mapping

    # -------------------------------------------------------------- persistence

    def as_dict(self, status: str) -> dict[str, Any]:
        environment = self.environment
        return {
            "schema": "aep-retrieval-session-v1",
            "dataset": environment.dataset,
            "qid": environment.qid,
            "perturbation": environment.perturbation,
            "question": environment.question,
            "declared_actions": list(self.declared_actions),
            "environment_actions": list(environment.available_actions),
            "status": status,
            "actions_used": len(self.observations),
            "tool_path": list(self.tool_path),
            "route_gaps": list(self.route_gaps),
            "chunks_read_ids": sorted(self.read_ids()),
            "retrieval_logs": list(self.retrieval_logs),
        }


def write_session(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Atomic durable write, matching the runtime's own state-writing discipline."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    handle_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent), text=True
    )
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return {"path": str(target), "bytes": target.stat().st_size}


def read_session(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------- boundary


def validate_result(result: dict[str, Any], session_file: str) -> dict[str, Any]:
    """Program-owned acceptance gate attached to the `agent()` boundary.

    Only publicly derivable facts about the persisted retrieval session are
    inspected. The gold answer and the gold evidence ids are never read here, so
    no validation problem this gate returns can leak the expected answer back to
    the Host through `previous_validation_problems`.
    """
    problems: list[str] = []
    status = result.get("status")
    answer = result.get("answer")
    cited = result.get("cited_chunk_ids")
    tool_path = result.get("tool_path")

    if status not in ("answered", "insufficient"):
        problems.append("status must be 'answered' or 'insufficient'")
    if not isinstance(tool_path, list):
        problems.append("tool_path must be an array")
    if isinstance(cited, list) and len(cited) != len(set(map(str, cited))):
        problems.append("cited_chunk_ids contains duplicates")

    session_path = Path(session_file)
    if not session_path.exists():
        problems.append("retrieval session file does not exist")
        read_ids: set[str] = set()
    else:
        read_ids = {str(item) for item in read_session(session_path).get("chunks_read_ids", [])}

    cited_ids = [str(item) for item in cited] if isinstance(cited, list) else []
    if status == "answered":
        if not isinstance(answer, str) or not answer.strip():
            problems.append("status is 'answered' but the answer is empty")
        if not cited_ids:
            problems.append("status is 'answered' but no chunk is cited")
        if not isinstance(tool_path, list) or not tool_path:
            problems.append("status is 'answered' but no retrieval tool was used")
    elif status == "insufficient":
        if isinstance(answer, str) and answer.strip():
            problems.append("status is 'insufficient' but an answer was returned")
        if cited_ids:
            problems.append("status is 'insufficient' but chunks were cited")

    unread = sorted(set(cited_ids) - read_ids)
    if unread:
        problems.append(
            "answer cites chunks that were not actually read: " + ", ".join(unread)
        )

    return {
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "read_chunk_ids": sorted(read_ids),
    }


# ------------------------------------------------------------ experiment scoring


def score_result(environment: Environment, result: dict[str, Any]) -> dict[str, Any]:
    """Experiment-side scoring. The only place the public gold answer is read."""
    gold_ids = set(environment.gold_evidence_ids)
    cited = {
        str(item)
        for item in (result.get("cited_chunk_ids") or [])
        if isinstance(item, str)
    }
    recall = (
        round(len(gold_ids & cited) / len(gold_ids), 4) if gold_ids else None
    )
    contained = bool(
        normalize(environment.gold_answer)
        and normalize(environment.gold_answer) in normalize(result.get("answer"))
    )
    answered = result.get("status") == "answered"
    if answered and contained:
        outcome = OUTCOME_ANSWERED_CORRECT
    elif answered:
        outcome = OUTCOME_ANSWERED_WRONG
    else:
        outcome = OUTCOME_REFUSED

    answerable = environment.evidence_present
    if not answerable:
        adaptive_success: bool | None = outcome == OUTCOME_REFUSED
    elif outcome != OUTCOME_ANSWERED_CORRECT:
        adaptive_success = False
    elif recall is None:
        adaptive_success = True
    elif environment.exact_gold_ids:
        # The public record names the gold evidence set, so reaching all of it
        # is the meaningful bar.
        adaptive_success = recall == 1.0
    else:
        # The lexical containment proxy over-counts evidence, so requiring the
        # full proxied set would measure proxy noise rather than route
        # flexibility. Reaching any gold evidence is the bar here.
        adaptive_success = recall > 0.0

    return {
        "answerable": answerable,
        "evidence_mode": "exact" if environment.exact_gold_ids else "proxy",
        "gold_evidence_count": len(gold_ids),
        "evidence_recall": recall,
        "contain_match": contained,
        "outcome": outcome,
        "adaptive_success": adaptive_success,
        "false_answer": (not answerable) and outcome == OUTCOME_ANSWERED_WRONG,
        "over_citation": len(cited - gold_ids) if gold_ids else None,
    }


def build_report(
    *,
    instance_id: str,
    implementation: str,
    routes_mode: str,
    status: str,
    session: RetrievalSession | None = None,
    result: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    rounds: int = 1,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "implementation": implementation,
        "routes_mode": routes_mode,
        "status": status,
        "rounds": rounds,
        "declared_actions": list(session.declared_actions) if session else [],
        "environment_actions": list(session.environment.available_actions) if session else [],
        "actions_used": len(session.observations) if session else 0,
        "tool_path": list(session.tool_path) if session else [],
        "route_gaps": list(session.route_gaps) if session else [],
        "result": result,
        "validation": validation,
        "score": score,
        "error": error,
    }


def write_report(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    return write_session(path, report)