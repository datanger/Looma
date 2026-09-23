"""Control-flow tests for the public-data retrieval-perturbation workload.

These tests import no framework and need no network. They run against the
hand-written fixture corpus in the public files' shape, which exists only to
verify control flow and must never produce a reported number.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.workloads.retrieval_perturbation.driver import AdaptiveRetrievalDriver
from experiments.workloads.retrieval_perturbation.injectors import (
    ACTION_LIST_CHUNKS,
    ACTION_READ_CHUNK,
    DEV_ROUTE_SET,
    EVAL_PERTURBATIONS,
    HOST_NATIVE_ROUTE_SET,
    PERTURBATIONS,
    Environment,
    build_environment,
    split_of,
)
from experiments.workloads.retrieval_perturbation.instance import (
    select_instances,
    write_payload,
)
from experiments.workloads.retrieval_perturbation.protocol import (
    MAX_ACTIONS_PER_ROUND,
    RetrievalSession,
    build_report,
    score_result,
    validate_result,
    write_session,
)
from experiments.workloads.retrieval_perturbation.run_perturbation import (
    PARADIGMS,
    ROOT,
)

WORKLOAD = Path(__file__).resolve().parents[1] / "experiments" / "workloads" / "retrieval_perturbation"
FIXTURE_ROOT = WORKLOAD / "fixtures"
FIXTURE_DATASET = "fixture"


def instances():
    return select_instances(FIXTURE_ROOT, FIXTURE_DATASET)


def drive(environment: Environment, declared: tuple[str, ...]) -> RetrievalSession:
    session = RetrievalSession(environment, declared, max_actions=MAX_ACTIONS_PER_ROUND)
    driver = AdaptiveRetrievalDriver(environment.question)
    while True:
        request = driver.next_action(session)
        if request is None:
            break
        session.execute(request)
    return session


def host_drive(environment: Environment) -> tuple[RetrievalSession, dict]:
    """The Host route set is complete regardless of what the environment offers."""
    session = RetrievalSession(environment, HOST_NATIVE_ROUTE_SET, max_actions=MAX_ACTIONS_PER_ROUND)
    driver = AdaptiveRetrievalDriver(environment.question)
    while True:
        request = driver.next_action(session)
        if request is None:
            break
        session.execute(request)
    return session, driver.finish(session)


# ------------------------------------------------------------------ transforms


def test_perturbations_only_transform_public_chunks():
    """No transform may introduce text: every visible chunk must be a public chunk."""
    for dataset_instances in [instances()]:
        by_perturbation: dict[str, set[str]] = {}
        for instance in dataset_instances:
            by_perturbation.setdefault(instance.environment.perturbation, set()).update(
                instance.environment.chunks.values()
            )
        pristine = by_perturbation["baseline"]
        assert pristine, "the fixture corpus must be non-empty"
        for perturbation, texts in by_perturbation.items():
            assert texts <= pristine, (
                f"{perturbation} invented chunk text that is not in the public corpus"
            )


def test_corpus_truncation_is_a_subset_and_renaming_is_bijective():
    for instance in instances():
        environment = instance.environment
        original = {chunk.chunk_id: chunk.text for chunk in instance.corpus.chunks}
        assert len(environment.chunks) <= len(original)
        assert set(environment.origin_of) == set(environment.chunks)
        assert len(set(environment.origin_of.values())) == len(environment.origin_of)
        if environment.hides_ids:
            assert not (set(environment.chunks) & set(original)), (
                "source_id_renamed must not leave original identifiers visible"
            )
            assert set(environment.origin_of.values()) <= set(original)


def test_primary_tool_unavailable_removes_only_the_preferred_tool():
    for instance in instances():
        actions = instance.environment.available_actions
        if instance.environment.perturbation == "primary_tool_unavailable":
            assert "semantic_search" not in actions
            assert "keyword_search" in actions
        elif instance.environment.perturbation == "baseline":
            assert "semantic_search" in actions
        assert "read_chunk" in actions


# ---------------------------------------------------------------------- routes


def test_eval_split_is_not_satisfiable_with_the_frozen_dev_route():
    """The measured quantity: the dev route set must actually fail on eval."""
    blocked = 0
    for instance in instances():
        if split_of(instance.environment.perturbation) != "eval":
            continue
        environment = instance.environment
        if not environment.hides_ids:
            continue
        session = RetrievalSession(environment, DEV_ROUTE_SET)
        driver = AdaptiveRetrievalDriver(environment.question)
        while True:
            request = driver.next_action(session)
            if request is None:
                break
            try:
                session.execute(request)
            except Exception as exc:  # RouteMissing
                assert type(exc).__name__ == "RouteMissing"
                session.record_unsupported(exc)
                blocked += 1
    assert blocked >= len(EVAL_PERTURBATIONS) - 2, (
        "opaque-handle perturbations must force a route gap under the dev route set"
    )


def test_widening_the_route_set_removes_every_eval_route_gap():
    for instance in instances():
        environment = instance.environment
        if not environment.hides_ids:
            continue
        widened = DEV_ROUTE_SET + (ACTION_LIST_CHUNKS,)
        session = RetrievalSession(environment, widened)
        driver = AdaptiveRetrievalDriver(environment.question)
        while True:
            request = driver.next_action(session)
            if request is None:
                break
            session.execute(request)
        assert session.route_gaps == []
        assert any(
            observation["action"] == ACTION_LIST_CHUNKS for observation in session.observations
        ), "resolving opaque handles must actually use the added route"


def test_host_native_route_set_never_leaves_a_gap_anywhere():
    for instance in instances():
        session, _ = host_drive(instance.environment)
        assert session.route_gaps == []


# ----------------------------------------------------------------------- gate


def test_gate_feedback_never_leaks_the_gold_answer():
    """The recorded validity hole must stay closed on the public-data workload.

    Two properties are enforced, and the second matters as much as the first:

    * nothing oracle-shaped may appear in the feedback — no gold answer, no
      "expected ..." hint, no gold field;
    * the agent's *own* citation must still be reported. An over-sanitised gate
      that hid the offending id would make retry useless, so echoing the agent's
      output is required behaviour, not a leak.
    """
    assert "session_file" in inspect.signature(validate_result).parameters
    assert len(inspect.signature(validate_result).parameters) == 2, (
        "the gate must take only the result and the persisted session; any extra "
        "parameter is a route for oracle information to reach the boundary"
    )

    for instance in instances():
        environment = instance.environment
        gold = environment.gold_answer
        session = host_drive(environment)[0]
        agent_sentinel = "zz-agent-own-citation-zz"
        wrong = {
            "status": "answered",
            "answer": gold + " definitely-not-in-any-chunk",
            "cited_chunk_ids": [agent_sentinel],
            "tool_path": ["keyword_search:ready"],
            "confidence": 99,
        }
        with tempfile.TemporaryDirectory() as raw:
            session_file = Path(raw) / "session.json"
            write_session(session_file, session.as_dict("complete"))
            check = validate_result(wrong, str(session_file))

        assert check["status"] == "revise", "the gate must reject unread citations"
        assert set(check) == {"status", "problems", "read_chunk_ids"}
        blob = json.dumps(check, ensure_ascii=False).lower()
        assert "gold" not in blob
        assert gold.lower() not in blob, (
            f"gate feedback echoed the gold answer for {instance.instance_id}"
        )
        assert "expected" not in blob
        # ... while the agent's own bad citation is still reported back to it.
        assert agent_sentinel in blob


def test_scoring_is_separate_from_the_gate():
    """The gate must accept a structurally valid answer that scoring marks wrong."""
    instance = next(
        item for item in instances() if item.environment.evidence_present
    )
    environment = instance.environment
    session = host_drive(environment)[0]
    wrong_but_valid = {
        "status": "answered",
        "answer": "a plausible sentence that is not the gold answer",
        "cited_chunk_ids": sorted(session.read_ids())[:1],
        "tool_path": list(session.tool_path),
        "confidence": 50,
    }
    assert wrong_but_valid["cited_chunk_ids"], "the driver must read something on baseline"
    with tempfile.TemporaryDirectory() as raw:
        session_file = Path(raw) / "session.json"
        write_session(session_file, session.as_dict("complete"))
        check = validate_result(wrong_but_valid, str(session_file))
    assert check["status"] == "ready"
    scored = score_result(environment, wrong_but_valid)
    assert scored["contain_match"] is False
    assert scored["outcome"] == "answered_wrong"


# --------------------------------------------------------------------- control


def test_unanswerable_instances_are_classified_and_scored_separately():
    """The negative control must be identifiable and must not inflate adaptation."""
    found = False
    for instance in instances():
        environment = instance.environment
        if environment.evidence_present:
            continue
        found = True
        refusal = {
            "status": "insufficient",
            "answer": "",
            "cited_chunk_ids": [],
            "tool_path": ["keyword_search:ready"],
            "confidence": 0,
        }
        scored = score_result(environment, refusal)
        assert scored["answerable"] is False
        assert scored["adaptive_success"] is True
        assert scored["evidence_recall"] is None
    assert found, "the fixture corpus must exercise the unanswerable control"


def test_payload_handed_to_paradigms_carries_no_gold_label():
    """The payload must carry no gold *label*.

    Note what is deliberately not asserted: the expected answer does not appear
    in the payload as a *string* is impossible to guarantee, because the answer
    is derivable from the public corpus by construction — that derivation is the
    task. What must not leak is a gold field, a gold evidence id list, or the
    original-id mapping a Host could dereference against a labelled split.
    """
    probes = [
        instance
        for instance in instances()
        if instance.environment.gold_answer and instance.environment.evidence_present
    ]
    assert probes
    for instance in probes:
        payload = instance.environment.payload()
        assert "gold" not in json.dumps(payload, ensure_ascii=False).lower()
        assert "origin_of" not in payload
        assert set(payload) == {
            "schema", "dataset", "qid", "perturbation", "seed",
            "question", "chunks", "available_actions", "hides_ids", "manifest",
        }
        assert not any(
            key in payload for key in ("answer", "gold_answer", "label", "target")
        )
        rebuilt = Environment.from_payload(payload)
        assert rebuilt.gold_evidence_ids == ()
        assert rebuilt.gold_answer == ""
        assert rebuilt.evidence_present is False


def test_looma_application_declares_no_route_and_is_unchanged_between_batches():
    entry = PARADIGMS["looma"]
    application = WORKLOAD / entry["code"]["dev"][0]
    host = WORKLOAD / entry["host_file"]
    source = application.read_text(encoding="utf-8")
    assert "capture" not in source
    assert "token_provider" not in source
    assert entry["code"]["dev"] == entry["code"]["widened"], (
        "the AEP application must be the same file in both batches"
    )
    assert host.exists(), "the Host simulator is the only route owner"
    report = build_report(
        instance_id="x",
        implementation="looma",
        routes_mode="host_native",
        status="complete",
    )
    assert report["declared_actions"] == []


# ------------------------------------------------------------------- end to end


def test_runner_end_to_end_on_fixture_labels_the_run_as_fixture():
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "fixture.json"
        completed = subprocess.run(
            [
                sys.executable, "-m",
                "experiments.workloads.retrieval_perturbation.run_perturbation",
                "--data-root", str(FIXTURE_ROOT),
                "--datasets", FIXTURE_DATASET,
                "--output", str(output),
            ],
            cwd=ROOT,
            env={
                "PYTHONPATH": f"{ROOT}:{ROOT / 'src'}",
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(Path.home()),
            },
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 0, completed.stderr[-2000:]
        payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["mode"] == "fixture"
    assert "fixture_warning" in payload
    assert payload["provenance"][FIXTURE_DATASET]["mode"] == "fixture"
    assert {row["perturbation"] for row in payload["rows"]} == set(PERTURBATIONS)
    assert all(row["status"] != "harness_error" for row in payload["rows"])

    by_key = {(row["implementation"], row["routes_mode"]): row for row in payload["table"]}
    dev_routes = by_key[("direct_sdk", "dev")]
    widened_routes = by_key[("direct_sdk", "widened")]
    looma_dev = by_key[("looma", "dev")]
    looma_widened = by_key[("looma", "widened")]

    assert dev_routes["eval_route_gaps"] > 0
    assert widened_routes["eval_route_gaps"] == 0
    assert widened_routes["adaptive_success_eval"] > dev_routes["adaptive_success_eval"]
    assert looma_dev["eval_route_gaps"] == 0
    assert looma_widened["eval_route_gaps"] == 0
    assert looma_dev["application_sha256"] == looma_widened["application_sha256"]
    assert looma_dev["route_declaration_delta_sloc"] == 0
    assert looma_widened["route_declaration_delta_sloc"] == 0
    assert widened_routes["route_declaration_delta_sloc"] > 0
    # Widening is an edit for the application-owned route and a no-op for AEP.
    assert widened_routes["application_sha256"] != dev_routes["application_sha256"]
    assert widened_routes["application_sloc"] > dev_routes["application_sloc"]
    # Across the two batches AEP's application is the same code, byte for byte.
    assert looma_dev["application_sloc"] == looma_widened["application_sloc"]
    # AEP's application is *larger*; the claim is route stability, not fewer lines.
    assert looma_dev["application_sloc"] >= dev_routes["application_sloc"]


def test_expect_public_refuses_a_fixture_corpus():
    completed = subprocess.run(
        [
            sys.executable, "-m",
            "experiments.workloads.retrieval_perturbation.run_perturbation",
            "--data-root", str(FIXTURE_ROOT),
            "--datasets", FIXTURE_DATASET,
            "--expect-public",
        ],
        cwd=ROOT,
        env={
            "PYTHONPATH": f"{ROOT}:{ROOT / 'src'}",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
        },
        text=True,
        capture_output=True,
    )
    assert completed.returncode != 0
    assert "not a pinned public benchmark dataset" in completed.stderr