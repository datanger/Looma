# AEP-GEPA Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a general-purpose, Host-native GEPA-style reflective optimization capability while preserving Looma's AEP primitives, pure-Python wheel, and replay/resume contracts.

**Architecture:** Add a model-independent `looma.optimization` protocol and deterministic state/Pareto helpers. Workflows use `step()` for evaluation and state transitions and `agent()` for reflection/proposals; no Looma code imports an LLM client or launches an Agent. The first release keeps the optimization loop explicit in ordinary Python so control flow and acceptance criteria remain program-owned.

**Tech Stack:** Python 3.10+, dataclasses, existing Looma JSON normalization/schema validation, pytest, subprocess restart tests, setuptools wheel packaging.

---

## Task 1: Add optimization protocol types

**Files:**

- Create: `src/looma/optimization/__init__.py`
- Create: `src/looma/optimization/protocol.py`
- Create: `tests/test_optimization_protocol.py`

- [x] **Step 1: Write failing protocol tests**

The tests must cover stable candidate identity, aligned per-example values, JSON normalization, and rejection of non-string candidate components:

~~~python
from looma.optimization import CandidateProposal, EvaluationBatch, candidate_id
from looma.exceptions import SerializationError
import pytest

def test_candidate_id_is_stable_for_mapping_order():
    assert candidate_id({"b": "B", "a": "A"}) == candidate_id({"a": "A", "b": "B"})

def test_candidate_proposal_normalizes_to_json():
    proposal = CandidateProposal(
        candidate={"system_prompt": "Use evidence."},
        components_to_update=["system_prompt"],
        rationale="The previous candidate omitted evidence checks.",
    )
    assert proposal.to_json()["candidate"]["system_prompt"] == "Use evidence."

def test_candidate_id_rejects_non_string_values():
    with pytest.raises(SerializationError):
        candidate_id({"prompt": 3})

def test_evaluation_batch_requires_aligned_values():
    with pytest.raises(ValueError, match="same length"):
        EvaluationBatch(outputs=["ok"], scores=[])
~~~

- [x] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q tests/test_optimization_protocol.py`

Expected: import failure because `looma.optimization` does not exist.

- [x] **Step 3: Implement the protocol**

Create `protocol.py` with:

~~~python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from ..exceptions import SerializationError
from ..serde import json_hash, normalize_json

Candidate: TypeAlias = dict[str, str]

def candidate_id(candidate: Mapping[str, str]) -> str:
    normalized = {str(key): value for key, value in sorted(candidate.items())}
    if any(not isinstance(value, str) for value in normalized.values()):
        raise SerializationError("candidate component values must be strings")
    return json_hash(normalized)[:24]

@dataclass(frozen=True)
class EvaluationBatch:
    outputs: list[Any]
    scores: list[float]
    trajectories: list[Any] | None = None
    objective_scores: list[dict[str, float]] | None = None
    side_information: list[Any] | None = None
    metric_calls: int | None = None

    def __post_init__(self):
        size = len(self.outputs)
        if len(self.scores) != size:
            raise ValueError("outputs and scores must have the same length")
        for name in ("trajectories", "objective_scores", "side_information"):
            values = getattr(self, name)
            if values is not None and len(values) != size:
                raise ValueError(f"outputs and {name} must have the same length")

    def to_json(self) -> dict[str, Any]:
        return normalize_json({
            "outputs": self.outputs,
            "scores": self.scores,
            "trajectories": self.trajectories,
            "objective_scores": self.objective_scores,
            "side_information": self.side_information,
            "metric_calls": self.metric_calls,
        })

@dataclass(frozen=True)
class CandidateProposal:
    candidate: Candidate
    components_to_update: list[str]
    rationale: str = ""
    hypothesis: str = ""
    targeted_failure: str = ""

    def to_json(self) -> dict[str, Any]:
        return normalize_json(self.__dict__)

class OptimizationAdapter(Protocol):
    def evaluate(
        self, batch: list[Any], candidate: Candidate, capture_traces: bool = False
    ) -> EvaluationBatch:
        raise NotImplementedError

    def make_reflective_dataset(
        self,
        candidate: Candidate,
        evaluation: EvaluationBatch,
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        raise NotImplementedError
~~~

Export only `Candidate`, `CandidateProposal`, `EvaluationBatch`, `OptimizationAdapter`, and `candidate_id`. Do not add a model or Agent dependency.

- [x] **Step 4: Run the focused tests**

Run: `pytest -q tests/test_optimization_protocol.py`

Expected: all protocol tests pass.

- [x] **Step 5: Commit**

~~~bash
git add src/looma/optimization tests/test_optimization_protocol.py
git commit -m "feat: add AEP optimization protocol"
~~~

## Task 2: Implement deterministic Pareto tracking

**Files:**

- Create: `src/looma/optimization/pareto.py`
- Create: `tests/test_optimization_pareto.py`

- [x] **Step 1: Write failing tests**

Cover strict dominance, complementary candidates, deterministic tie-breaking, and missing-dimension rejection:

~~~python
from looma.optimization.pareto import ParetoFrontier

def test_dominated_candidate_is_removed():
    frontier = ParetoFrontier().add("weak", {"a": 0.5, "b": 0.5})
    frontier = frontier.add("strong", {"a": 0.6, "b": 0.5})
    assert frontier.ids == ("strong",)

def test_complementary_candidates_survive():
    frontier = ParetoFrontier().add("left", {"a": 1.0, "b": 0.0})
    frontier = frontier.add("right", {"a": 0.0, "b": 1.0})
    assert frontier.ids == ("left", "right")

def test_equal_scores_are_sorted_deterministically():
    frontier = ParetoFrontier().add("z", {"a": 1.0}).add("a", {"a": 1.0})
    assert frontier.ids == ("a", "z")
~~~

- [x] **Step 2: Run the tests and verify they fail**

Run: `pytest -q tests/test_optimization_pareto.py`

Expected: import failure for `looma.optimization.pareto`.

- [x] **Step 3: Implement immutable frontier operations**

Implement:

~~~python
@dataclass(frozen=True)
class ParetoFrontier:
    scores: dict[str, dict[str, float]] = field(default_factory=dict)
    ids: tuple[str, ...] = ()

    def add(self, candidate_id: str, scores: Mapping[str, float]) -> "ParetoFrontier":
        raise NotImplementedError

    def contains(self, candidate_id: str) -> bool:
        raise NotImplementedError
~~~

Add a candidate only when no existing candidate dominates it; remove candidates it dominates; sort IDs lexicographically. Require identical score dimensions for every comparison. Copy nested mappings on every update so an old replay value cannot be mutated.

- [x] **Step 4: Run the tests**

Run: `pytest -q tests/test_optimization_pareto.py`

Expected: all Pareto tests pass.

- [x] **Step 5: Commit**

~~~bash
git add src/looma/optimization/pareto.py tests/test_optimization_pareto.py
git commit -m "feat: add deterministic Pareto frontier"
~~~

## Task 3: Add serializable optimization state and acceptance gates

**Files:**

- Create: `src/looma/optimization/state.py`
- Create: `tests/test_optimization_state.py`

- [x] **Step 1: Write failing state tests**

Cover state round-trip, budget counters, unknown component rejection, hard constraints, and no-mutation-on-rejection:

~~~python
from looma.optimization import CandidateProposal
from looma.optimization.state import OptimizationState, accept_proposal

def test_state_round_trip_is_json_compatible():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    assert OptimizationState.from_json(state.to_json()) == state

def test_unknown_component_does_not_mutate_state():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"other": "bad"}, ["other"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.0},
    )
    assert result.accepted is False
    assert result.state == state

def test_hard_constraint_rejects_higher_score():
    state = OptimizationState.initialize({"prompt": "start"}, max_iterations=3)
    result = accept_proposal(
        state,
        CandidateProposal({"prompt": "unsafe"}, ["prompt"]),
        scores={"case": 1.0},
        parent_scores={"case": 0.5},
        hard_constraints=[lambda candidate: candidate["prompt"] != "unsafe"],
    )
    assert result.accepted is False
~~~

- [x] **Step 2: Run the tests and verify they fail**

Run: `pytest -q tests/test_optimization_state.py`

Expected: import failure for `looma.optimization.state`.

- [x] **Step 3: Implement state and acceptance**

Define JSON-compatible dataclasses:

~~~python
@dataclass(frozen=True)
class OptimizationConfig:
    max_iterations: int
    max_metric_calls: int | None = None
    score_threshold: float | None = None
    no_improvement_patience: int | None = None

@dataclass(frozen=True)
class OptimizationState:
    seed_candidate: Candidate
    candidates: dict[str, Candidate]
    frontier: ParetoFrontier
    iteration: int
    metric_calls: int
    no_improvement_rounds: int
    status: str
    config: OptimizationConfig

    @classmethod
    def initialize(cls, seed_candidate, *, max_iterations):
        raise NotImplementedError

    @property
    def should_stop(self) -> bool:
        raise NotImplementedError

    def to_json(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_json(cls, value):
        raise NotImplementedError
~~~

Implement `accept_proposal()` returning `AcceptanceResult(state, accepted, reason)`. It must reject unknown components, non-string values, failed hard constraints, and candidates that do not meet the configured acceptance criterion. Use `normalize_json()` and `candidate_id()`; do not persist callables, model clients, or arbitrary Python objects.

- [x] **Step 4: Run the tests**

Run: `pytest -q tests/test_optimization_state.py`

Expected: all state and acceptance tests pass.

- [x] **Step 5: Commit**

~~~bash
git add src/looma/optimization/state.py tests/test_optimization_state.py
git commit -m "feat: add durable optimization state and acceptance gates"
~~~

## Task 4: Route reflective proposals through the Host Agent

**Files:**

- Create: `src/looma/optimization/engine.py`
- Modify: `src/looma/optimization/__init__.py`
- Create: `tests/test_optimization_engine.py`

- [x] **Step 1: Write failing engine tests**

Test payload construction and monkeypatch the existing `agent()` function to prove no model client is used:

~~~python
def test_reflection_payload_contains_asi_and_budget():
    payload = build_reflection_input(
        candidate={"prompt": "start"},
        evaluation=EvaluationBatch(
            outputs=["bad"],
            scores=[0.0],
            trajectories=[{"error": "missing evidence"}],
            side_information=[{"error": "missing evidence"}],
        ),
        frontier_ids=["seed"],
        metric_calls=4,
        remaining_budget=6,
    )
    assert payload["evaluation"]["side_information"][0]["error"] == "missing evidence"
    assert payload["budget"]["remaining_metric_calls"] == 6

def test_request_reflection_delegates_to_agent(monkeypatch):
    seen = {}
    def fake_agent(**kwargs):
        seen.update(kwargs)
        return CandidateProposal({"prompt": "updated"}, ["prompt"])
    monkeypatch.setattr("looma.optimization.engine.agent", fake_agent)
    proposal = request_reflection(
        task="Improve the prompt.",
        candidate={"prompt": "start"},
        evaluation=EvaluationBatch(outputs=["bad"], scores=[0.0]),
        frontier_ids=["seed"],
        metric_calls=1,
        remaining_budget=9,
    )
    assert proposal.candidate["prompt"] == "updated"
    assert seen["output_schema"] is CandidateProposal
~~~

- [x] **Step 2: Run the tests and verify they fail**

Run: `pytest -q tests/test_optimization_engine.py`

Expected: import failure for `looma.optimization.engine`.

- [x] **Step 3: Implement pure payload construction and Host delegation**

Implement `build_reflection_input()` and `request_reflection()`. The latter must call the existing `looma.api.agent` with `output_schema=CandidateProposal`. It must not create a client, invoke a subprocess, or retry internally. Export these helpers from `looma.optimization`.

- [x] **Step 4: Run the tests**

Run: `pytest -q tests/test_optimization_engine.py`

Expected: all engine tests pass.

- [x] **Step 5: Commit**

~~~bash
git add src/looma/optimization/engine.py src/looma/optimization/__init__.py tests/test_optimization_engine.py
git commit -m "feat: route optimization reflection through host agent"
~~~

## Task 5: Prove process restart, replay, and isolation

**Files:**

- Create: `tests/test_optimization_restart.py`
- Modify: `tests/test_run_isolation.py` only if a shared helper is required

- [x] **Step 1: Add a temporary suspended workflow**

The subprocess test must evaluate a candidate through `step()`, increment a side-effect counter, call `request_reflection()`, and suspend with exit code `75`. After writing a valid `CandidateProposal` result file, invoke the same original command and assert:

- the evaluation side effect count remains one;
- completed evaluation/state events are not duplicated;
- the final candidate is accepted;
- the frontier contains the accepted candidate.

- [x] **Step 2: Add invalid-result and guarded-handoff cases**

Use the existing `looma handoff` command to prove malformed proposal JSON, unknown components, and failed hard constraints cannot resume or mutate state. Assert exit code `76` for handoff validation failures.

- [x] **Step 3: Add two-instance isolation**

Run the same workflow with `LOOMA_RUN_KEY=job-a` and `LOOMA_RUN_KEY=job-b`. Assert each run has independent state, event files, candidates, and frontier.

- [x] **Step 4: Run the process tests**

Run: `pytest -q tests/test_optimization_restart.py tests/test_run_isolation.py`

Expected: all restart, guarded-resume, and isolation tests pass.

- [x] **Step 5: Commit**

~~~bash
git add tests/test_optimization_restart.py tests/test_run_isolation.py
git commit -m "test: cover optimization restart and isolation"
~~~

## Task 6: Add a runnable AEP + GEPA example

**Files:**

- Create: `examples/gepa_optimization/workflow.py`
- Create: `examples/gepa_optimization/README.md`
- Modify: `examples/README.md`
- Create: `tests/test_gepa_example.py`

- [x] **Step 1: Write the smoke test**

Run the example in a temporary `LOOMA_STATE_DIR`; assert the first process exits `75`, write a valid proposal to the emitted `result_file`, resume the original command, and assert the final output contains the accepted candidate and frontier summary.

- [x] **Step 2: Implement the deterministic example**

Use a small adapter that scores whether candidate text causes a deterministic transformation. The example must show `@workflow`, a `step()` around `adapter.evaluate`, `request_reflection()` with the evaluation payload, and a `step()` around `accept_proposal`. It must not call a model, network service, external GEPA package, or subprocess Agent. The README must state that the Host Agent supplies the proposal during the `script2agent` pause.

- [x] **Step 3: Run the example test**

Run: `pytest -q tests/test_gepa_example.py`

Expected: suspension and same-command resume complete without repeating the evaluation side effect.

- [x] **Step 4: Commit**

~~~bash
git add examples/gepa_optimization tests/test_gepa_example.py examples/README.md
git commit -m "feat: add AEP GEPA optimization example"
~~~

## Task 7: Update documentation, Skill, and packaging

**Files:**

- Modify: `README.md`
- Modify: `docs/agent-embedded-programming.md`
- Modify: `src/looma/skills/agent-embedded-programming/SKILL.md`
- Modify: `release/RELEASE_NOTES.md`
- Modify: `pyproject.toml` only if package discovery requires it
- Create: `tests/test_optimization_packaging.py`

- [x] **Step 1: Add documentation tests**

Assert that the packaged Skill mentions candidate evaluation, ASI, Pareto frontier, Host reflection through `agent()`, and the prohibition on direct model clients.

- [x] **Step 2: Document the public contracts**

Document the adapter, explicit Python optimization loop, trace/ASI payload, Pareto behavior, acceptance gates, budgets, and replay behavior. Explain that an external GEPA backend may implement the same protocol later, but is not a core dependency.

- [x] **Step 3: Verify wheel contents**

Run:

~~~bash
python -m build --wheel --no-isolation
unzip -l dist/*.whl | rg 'looma/optimization|looma/skills/agent-embedded-programming/SKILL.md'
~~~

Expected: optimization modules and the updated Skill are present; wheel metadata contains no model SDK dependency.

- [x] **Step 4: Run the complete suite**

Run:

~~~bash
pytest -q
python -m compileall -q src examples
~~~

Expected: all tests pass and compilation exits `0`.

- [x] **Step 5: Commit**

~~~bash
git add README.md docs/agent-embedded-programming.md src/looma/skills/agent-embedded-programming/SKILL.md release/RELEASE_NOTES.md pyproject.toml tests/test_optimization_packaging.py
git commit -m "docs: document AEP GEPA capability"
~~~

## Task 8: Final completion audit

- [x] **Step 1: Verify the public API**

Run:

~~~bash
python -c 'from looma import agent, step, workflow; import looma.optimization as optimization; print(agent.__name__, step.__name__, workflow.__name__, sorted(optimization.__all__))'
~~~

Expected: the three existing primitives import successfully and optimization exports are explicit.

- [x] **Step 2: Verify no direct model dependency**

Run:

~~~bash
rg -n 'openai|anthropic|litellm|codex|claude|subprocess.*agent' src/looma/optimization pyproject.toml
~~~

Expected: no direct model/client or Agent-launch code in the optimization package or dependency metadata.

- [x] **Step 3: Audit the implementation against the design**

Run:

~~~bash
git diff origin/main...HEAD --stat
git diff origin/main...HEAD -- src/looma/optimization tests examples/gepa_optimization docs/agent-embedded-programming.md
~~~

Confirm every requirement in `docs/superpowers/specs/2026-10-08-aep-gepa-capability-design.md` has implementation and test evidence before claiming completion.
