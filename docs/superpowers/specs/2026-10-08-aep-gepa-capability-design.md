# AEP-GEPA Capability Design

**Status:** Proposed

## Goal

Keep Looma a general-purpose Agent-Embedded Programming (AEP) runtime while adding GEPA-style reflective optimization for text-based candidates such as prompts, skills, agent instructions, policies, configurations, and code artifacts.

The capability must preserve Looma's existing host-native boundary: Python owns control flow and acceptance criteria, the current Host Coding Agent owns semantic reasoning and evidence acquisition, and Looma owns continuity, persistence, replay, and guarded resume.

## Scope

The first implementation provides a Looma-native optimization protocol and deterministic GEPA-style engine:

- candidate components represented as JSON-compatible text mappings;
- an adapter protocol for candidate evaluation and trace/ASI extraction;
- reflective proposal through the existing `agent()` boundary;
- deterministic acceptance gates and stop conditions;
- instance/objective-aware Pareto frontier tracking;
- durable optimization state and restart/resume behavior;
- process-level tests and a runnable AEP + GEPA example;
- documentation and bundled Skill alignment.

The first implementation does not vendor or require the external `gepa` package, LiteLLM, OpenAI SDKs, Anthropic SDKs, or any other direct LLM client. An external GEPA backend may be added later through the protocol without changing the AEP core.

## Non-goals

- launching an Agent, subagent, CLI, SDK, or LLM process from Looma;
- replacing `@workflow`, `step()`, or `agent()` with a graph DSL;
- hiding retries or scheduling inside the optimization engine;
- treating a scalar score as sufficient when a hard acceptance rule rejects the candidate;
- restoring Python call stacks or rewriting Python source during resume;
- making GEPA-specific optimization mandatory for ordinary Looma workflows.

## Public model

The existing programming model remains authoritative:

```python
@workflow
def optimize_system(seed_candidate, dataset):
    state = optimization.initialize(seed_candidate)

    while not state.should_stop:
        candidate = optimization.select_candidate(state)
        evaluation = step(adapter.evaluate, dataset.sample(), candidate)

        proposal = agent(
            task="分析执行轨迹和 ASI，提出可验证的候选组件更新。",
            input={
                "candidate": candidate,
                "evaluation": evaluation,
                "frontier": state.frontier_summary,
            },
            input_schema=optimization.reflection_input_schema(),
            output_schema=optimization.CandidateProposal,
        )

        state = step(optimization.accept_proposal, state, proposal)

    return state.best_candidate
```

The optimization module is a reusable helper layer, not a fourth execution primitive. `step()` protects evaluation and state mutations; `agent()` remains the only semantic boundary.

## Architecture

### 1. Optimization protocol

Add a focused `src/looma/optimization/` package:

- `protocol.py` — `Candidate`, `EvaluationBatch`, `CandidateProposal`, `OptimizationAdapter`, and JSON-compatible type contracts;
- `pareto.py` — deterministic dominance, frontier update, candidate selection, and stable tie-breaking;
- `state.py` — serializable optimization state, candidate identities, evaluation cache references, budget counters, and stop status;
- `engine.py` — deterministic proposal/evaluation orchestration that calls the existing `step()` and `agent()` APIs rather than model clients;
- `schema.py` — input/result schemas for proposals and adapter payloads, reusing Looma's schema validation primitives;
- `__init__.py` — narrow public exports.

The package must not import a model SDK. Reflection is expressed as a normal `agent()` call made by the workflow or by a thin helper that delegates to the current runtime.

### 2. Candidate and evaluation contracts

The canonical candidate is a mapping from component name to text:

```python
Candidate = dict[str, str]
```

An adapter evaluates a candidate over a batch and returns:

- one output per input;
- one higher-is-better score per input;
- optional objective score mappings;
- optional opaque trajectories;
- optional actionable side information (ASI), including errors, constraint violations, profiling data, tool traces, or evaluator feedback.

The engine treats outputs and trajectories as opaque JSON-compatible data. The adapter owns domain interpretation and must return structured per-example failures instead of raising for an individual failed example. Systemic failures remain exceptions and fail the workflow according to normal Looma semantics.

### 3. Reflective proposal boundary

The reflection payload is built from:

- the selected parent candidate;
- the minibatch evaluation;
- the component names selected for update;
- the relevant trajectories and ASI;
- the current frontier summary;
- the remaining evaluation budget and acceptance requirements.

The Host Coding Agent returns a structured `CandidateProposal` through `agent()`. The proposal must contain a candidate update and may contain rationale, hypothesis, targeted failure mode, and proposed validation notes. These fields are business data written to the Agent result file; they never enter `agent2script`.

Invalid proposal schema, non-JSON values, unknown components, or updates outside the declared candidate scope are rejected before state mutation.

### 4. Pareto frontier

The frontier stores candidate identities with their per-instance and optional per-objective scores. A candidate is dominated only when another candidate is no worse on every tracked dimension and strictly better on at least one. Candidates that solve different subsets remain available for future mutation or merge.

All ordering and tie-breaking must be deterministic. Candidate identity is a content hash over normalized component text and relevant optimization metadata. The state stores the frontier, candidate registry, accepted parent links, and the evaluation evidence needed to reproduce decisions.

### 5. Acceptance and stopping

The default acceptance criterion is strict minibatch improvement with optional hard constraints. The protocol must allow a workflow to supply a deterministic acceptance function for domain gates such as:

- no hard constraint violation;
- no regression on a fixed validation set;
- minimum score or objective threshold;
- required evidence or artifact validation;
- cost/latency ceilings.

Stopping conditions are explicit configuration, such as maximum iterations, maximum metric calls, score threshold, no-improvement patience, or a host-controlled stop signal. The engine must not introduce a hidden retry loop.

### 6. Durable state and replay

Optimization state is persisted through Looma's existing durable event model. The state must be reconstructible after process restart and must not contain live model clients, file handles, sockets, threads, processes, or arbitrary Python objects.

At minimum, replay-visible events must identify:

- optimization instance and seed candidate;
- selected parent and sampled batch identifiers;
- evaluation result and metric-call count;
- reflection request/result references;
- proposed candidate identity;
- acceptance/rejection decision and reason;
- frontier update;
- budget and stop status.

The existing `script2agent` / `agent2script` contract remains unchanged. A suspended reflection re-runs the original command, replays completed evaluations and accepted state transitions, and resumes at the same `agent()` boundary.

## Failure handling

- Individual evaluation errors become structured failed examples with deterministic fallback scores and ASI.
- Systemic adapter errors fail the workflow and remain inspectable.
- Invalid Agent proposals are rejected by result schema validation before acceptance.
- Candidate mutations that violate component scope or JSON compatibility are rejected deterministically.
- Replay divergence raises `ReplayMismatchError`; the engine never silently rebuilds history.
- A failed or interrupted optimization must not leave an active pointer that causes an unrelated invocation to resume the wrong optimization instance.

## File and documentation impact

Implementation should touch only focused units:

- Create: `src/looma/optimization/` protocol, Pareto, state, engine, schema, and exports;
- Modify: `src/looma/api.py` only if a public helper needs to be exposed, without changing the three core primitives;
- Modify: `src/looma/runtime.py` only where optimization event references must integrate with existing durable state;
- Create: `tests/test_optimization_protocol.py`, `tests/test_optimization_pareto.py`, and `tests/test_optimization_restart.py`;
- Create: one example under `examples/` showing a multi-round reflective optimization loop with a deterministic evaluator;
- Modify: `docs/agent-embedded-programming.md`, `README.md`, `examples/README.md`, and `src/looma/skills/agent-embedded-programming/SKILL.md` to describe the capability and its host-native boundary.

No GEPA-specific dependency should be added to the base wheel. If an external backend is introduced later, it must be an optional extra and implement the same adapter/proposal contracts.

## Verification requirements

The feature is complete only when tests prove:

1. a candidate can be evaluated, reflected, accepted, and added to the frontier;
2. dominated candidates are removed while complementary candidates survive;
3. hard acceptance gates prevent invalid improvements;
4. evaluation and optimization state are not duplicated on replay;
5. a process restart during a pending reflection resumes the same workflow;
6. invalid proposal results cannot trigger state mutation or resume;
7. multiple independent optimization instances remain isolated;
8. the base package remains installable as a pure Python wheel without model SDK dependencies;
9. the bundled AEP Skill accurately describes the new optimization capability;
10. an external GEPA backend is not required for the core tests or example.

## Phased delivery

### Phase 1: Protocol and deterministic state

Implement candidate/evaluation/proposal contracts, content identities, serializable optimization state, Pareto dominance, acceptance, and unit tests.

### Phase 2: AEP host reflection and replay

Connect proposal generation to `agent()`, persist reflection references and optimization events, add result-schema and process-restart tests, and add the end-to-end example.

### Phase 3: Usability and integrations

Add inspect output, richer stop/budget policies, optional external GEPA adapter compatibility, and documentation/Skill updates based on the verified public behavior.
