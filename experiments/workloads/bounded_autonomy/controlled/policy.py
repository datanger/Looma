"""Deterministic driver policy: the fixture stand-in for the Host model.

Controlled mode replaces the model with one deterministic policy that is shared by every
paradigm, so that the *only* difference between paradigms is orchestration. The policy is
deliberately oracle-free:

* which sources it reads comes from the public task (`candidate_sources`) and from the
  environment catalog the application lets it see (`list_sources`);
* the decision is derived from source *content* ("score >= N", "signed review"), not from
  the scenario oracle.

The policy may ask for a `list` action whenever its declared reading plan cannot satisfy
the task requirements. Whether that request can be executed is exactly what each
paradigm's declared route set decides.
"""

from __future__ import annotations

import re
from typing import Any

from experiments.workloads.bounded_autonomy.controlled.protocol import ToolSession
from experiments.workloads.bounded_autonomy.controlled.protocol import ACTION_LIST


POLICY_THRESHOLD = re.compile(r"score\s*>=\s*(\d+)")
REVIEW_SCORE = re.compile(r"score\s+(\d+)")
SIGNED_REVIEW = "signed review"

NEED_AUTHORITATIVE_POLICY = "authoritative_policy"
NEED_REVIEW_EVIDENCE = "review_evidence"


class AdaptiveDriverPolicy:
    def __init__(self, public: dict[str, Any], *, max_reads: int = 8):
        self.public = public
        self.candidates = list(public.get("candidate_sources") or [])
        self.max_reads = max_reads
        self._plan_index = 0
        self._listed = False
        self._thorough = False
        self._unsupported: set[str] = set()

    # -- observation-driven state ------------------------------------------------

    def _needs(self, session: ToolSession) -> list[str]:
        documents = session.read_sources()
        needs: list[str] = []
        if self._best_policy(documents) is None:
            needs.append(NEED_AUTHORITATIVE_POLICY)
        if self._best_review(documents) is None:
            needs.append(NEED_REVIEW_EVIDENCE)
        return needs

    def _best_policy(self, documents: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        candidates = [
            document
            for document in documents.values()
            if document["kind"] == "policy" and document.get("authoritative")
        ]
        return candidates[0] if candidates else None

    def _best_review(self, documents: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        candidates = [
            document
            for document in documents.values()
            if document["kind"] == "review" and SIGNED_REVIEW in document["content"]
        ]
        return candidates[0] if candidates else None

    def note_feedback(self, problems: list[str] | None) -> None:
        """A rejected round makes the policy exhaustive, exactly as a real Agent would."""
        if problems:
            self._thorough = True

    def observe_unsupported(self, action: str) -> None:
        """The application has no route for this action; stop asking for it."""
        self._unsupported.add(action)

    def _next_discovered(self, session: ToolSession, needs: list[str]) -> str | None:
        already_read = session.read_ids()
        for entry in session.listed_sources():
            if entry["id"] in already_read or not entry["available"]:
                continue
            if NEED_AUTHORITATIVE_POLICY in needs and entry["kind"] == "policy" and entry["authoritative"]:
                return str(entry["id"])
            if NEED_REVIEW_EVIDENCE in needs and entry["kind"] == "review":
                return str(entry["id"])
        if self._thorough:
            for entry in session.listed_sources():
                if entry["id"] in already_read or not entry["available"]:
                    continue
                return str(entry["id"])
        return None

    # -- the action loop ---------------------------------------------------------

    def next_request(self, session: ToolSession) -> dict[str, Any]:
        """Return the next action request: `read`, `list`, or `finish`."""
        while self._plan_index < len(self.candidates) and len(session.read_ids()) < self.max_reads:
            source_id = self.candidates[self._plan_index]
            self._plan_index += 1
            if source_id in session.read_ids():
                continue
            return {"kind": "read", "source_id": source_id}

        needs = self._needs(session)
        if needs and not self._listed and ACTION_LIST not in self._unsupported:
            self._listed = True
            return {"kind": "list"}
        if needs and self._listed:
            discovered = self._next_discovered(session, needs)
            if discovered is not None and len(session.read_ids()) < self.max_reads:
                return {"kind": "read", "source_id": discovered}

        return {"kind": "finish", "result": self.compose_result(session)}

    def compose_result(self, session: ToolSession) -> dict[str, Any]:
        documents = session.read_sources()
        policy = self._best_policy(documents)
        review = self._best_review(documents)

        decision = "insufficient"
        rationale = "no authoritative policy evidence was obtainable"
        if policy is not None and review is not None:
            threshold = POLICY_THRESHOLD.search(policy["content"])
            score = REVIEW_SCORE.search(review["content"])
            if threshold and score:
                if int(score.group(1)) >= int(threshold.group(1)):
                    decision = "approve"
                    rationale = (
                        f"authoritative policy requires score >= {threshold.group(1)}; "
                        f"{review['source_id']} evidences score {score.group(1)} with a signed review"
                    )
                else:
                    decision = "reject"
                    rationale = (
                        f"authoritative policy requires score >= {threshold.group(1)}; "
                        f"{review['source_id']} evidences only score {score.group(1)}"
                    )
            else:
                rationale = "policy threshold or review score could not be read from the evidence"
        elif policy is not None:
            rationale = "the authoritative policy is known but no signed-review evidence exists"

        cited = list(documents)
        return {
            "decision": decision,
            "cited_source_ids": cited,
            "tool_path": list(session.tool_path),
            "rationale": rationale,
        }