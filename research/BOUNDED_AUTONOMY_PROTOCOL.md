# RQ2 — Bounded autonomy protocol

> **Scope and admissibility (2026-09-21).** This document specifies the *mechanism*
> protocol — what is perturbed, who owns the route, how the gate and the scoring are kept
> apart. The scenario suite it currently references
> (`experiments/workloads/bounded_autonomy/scenarios.json`) is **self-authored**, so no
> number measured on it is admissible as paper evidence.
>
> RQ2's reported results are re-based on **public benchmark instances** in
> `research/RETRIEVAL_PERTURBATION_PROTOCOL.md` (workload
> `experiments/workloads/retrieval_perturbation/`). The mechanism rules below apply there
> unchanged: split into development/held-out conditions, application-owned versus
> Host-owned route, an acceptance gate that sees no oracle, and a widening ablation in
> which only the declared route set changes.

## Claim being tested

AEP keeps application-level control flow fixed while allowing the already-running
Host Agent to choose and revise its internal tool/reasoning path inside an
explicit semantic boundary.

The target property is:

> interface stability with path autonomy.

This is not a claim that arbitrary Agent behavior is safe. Tool permissions are
Host-controlled and final continuation remains guarded by Result/Resume/Acceptance
contracts.

## Perturbation workload

The implemented suite currently includes seven scenarios, split into a **development
split** (published, used to author the applications) and a **held-out split** (used only
to score them):

| split | scenario | what is perturbed |
| --- | --- | --- |
| dev | `normal` | nothing |
| dev | `primary_tool_unavailable` | the preferred source is missing; a mirror is listed |
| dev | `conflicting_stale_note` | a stale note conflicts with the authoritative policy |
| eval | `renamed_authoritative_source` | the authoritative source was renamed; the new name is only visible to a discovery call |
| eval | `missing_review_replaced_by_audit` | the expected review is gone; an equivalent audit record exists under a different id |
| eval | `authoritative_only_after_discovery` | no authoritative source is reachable from the advertised entry point at all |
| eval | `insufficient_after_adaptation` | **control**: discovery is *not* required; the correct answer is "insufficient" |

Each scenario carries a `candidate_sources` list (what a discovery call may reveal) and a
`perturbation_axis` label. The Host receives only the public task/requirements, the
advertised entry sources and a deterministic source environment. It may call `list` and
`read` operations in any order.

The control scenario matters: without it, every held-out failure would be
"a scenario that requires discovery", and the suite would reward discovery as such rather
than rewarding answering correctly.

## The gate must not leak the oracle

`validator.py` exposes two deliberately separate functions:

* `validate_result(scenario_id, result)` — the **acceptance gate**. Its `problems` are the
  feedback that is fed back to the Agent on a retry, so it may only contain publicly
  derivable facts: an unknown/unavailable source id, too few sources, a missing required
  evidence kind, a missing authoritative source, an illegal decision value.
* `score_result(scenario_id, result)` — the **experiment-side scorer**. It knows the
  oracle (`expected_decision`, `expected_supporting_source_ids`) and computes
  `gate_ready / decision_correct / evidence_covered / task_success`.

A gate whose feedback says *"decision mismatch: expected insufficient"* hands the answer
back to the Agent and inflates every paradigm identically. `sanity.py` therefore reports
`gate_feedback_leaks_oracle` and `tests/test_bounded_autonomy.py` pins it. The current
suite reports `false`.

Acceptance is ultimately decided by the deterministic gate; a paradigm's own claim that
the task is complete is never sufficient.

### Known looseness

The `insufficient_after_adaptation` branch is the weakest part of the gate: "insufficient"
can be reached both by exhausting a declared route set and by genuinely concluding that no
authoritative evidence exists. Those are different behaviours and the current gate cannot
separate them, so that scenario should not carry weight in a claim about adaptation
quality. Tightening it requires evidence about *why* the Agent stopped, which the current
boundary does not record.

## Sanity baseline

`sanity.py` includes:

1. a **static-route diagnostic** that follows a predefined source path;
2. an **adaptive oracle** that is allowed to discover available sources.

The oracle is not an Agent and its success is **not** a paper result about AEP
intelligence. Its purpose is only to verify that the benchmark actually contains
perturbations where fixed routes break but adaptive paths can succeed.

## Real evaluation

Run the exact same `workflow.py` under each Host Agent. Record:

- scenario success;
- contract rejection/retry count;
- Host rounds;
- source/tool path;
- human intervention count;
- Workflow source hash;
- task quality.

No Workflow code may be modified between the unperturbed and perturbed tasks.

### Adaptive Task Success Rate

```text
ATSR = successful perturbed scenarios / all perturbed scenarios
```

Report the unperturbed normal case separately so that adaptive performance is not
inflated by easy nominal execution.

## Comparison to conventional workflows

For a fair framework comparison, conventional implementations must be given the
same tool environment and task information. We compare:

- `direct_sdk` — hand-written plan/execute loop;
- `langgraph` — `StateGraph` with explicit nodes and conditional edges;
- `microsoft_agent_framework` — the framework's `@workflow` / `build()` / `run()` form;
- `looma` — AEP Host-native execution.

The fixed route is a diagnostic lower bound, not a stand-in for all LangGraph or
Agent Framework programs.

### Route declaration vs host-owned routing

The controlled comparison (`controlled/`) makes the single difference between paradigms
explicit: **which action set the application's orchestration can issue.** Every paradigm
runs the same deterministic driver policy (`policy.py`, a model stand-in with no oracle
access), the same scenarios, and the same 3-round × 12-action-per-round budget.

Each conventional paradigm is run twice:

* `--routes dev` — the route set an author would freeze after the development split;
* `--routes widened` — the route set the held-out split turns out to require.

The widening ablation is itself the measurement: for a paradigm that owns its route set,
the held-out split forces a second edit, and `route_declaration_delta_sloc` is the size of
that edit. For AEP the application declares **no** action route
(`application_declared_actions == []`), the Host owns it, and the same file, hash and
command are used in both batches, so the delta is zero by construction.

ATSR is reported per split:

```text
ATSR_dev  = successes on the development split / |dev|
ATSR_eval = successes on the held-out split / |eval|
```

`route_gaps` are recorded as data (which declared action was missing), never as a silent
success or a crash: `ToolSession` raises `RouteMissing`, the harness records it, and the
requesting implementation observes "that action is not available to you" as an ordinary
observation.

### Threats to validity

1. **Model stand-in.** The numbers below measure route flexibility and orchestration
   overhead, not Agent output quality. Quality claims need the model-backed runs.
2. **One mechanism.** The held-out discriminator is essentially "can the orchestration
   discover an unadvertised source". Unavailability and conflict axes appear only in the
   development split.
3. **Per-round budget.** Actions are capped per round, not for the whole run, and the
   retry dimension is barely exercised (`rounds == 1` in every current row).
4. **Two of four paradigms are not yet executed.** `langgraph` and
   `microsoft_agent_framework` need pinned dependencies
   (`experiments/requirements-phase1.txt`) and their rows are only produced in CI.

## Stability interaction

Every Host result is validated after the autonomous trajectory. The experiment
therefore measures whether stronger local autonomy can coexist with deterministic
boundary acceptance, rather than granting the Agent control of global program
continuation.

## Boundary contracts used by the implemented Workflow

The current bounded-autonomy Workflow declares both an Agent `input_schema`
and a structured result schema. Therefore the Host is free to change its internal
tool path, but it cannot receive structurally malformed task context through the
declared boundary, and its final result must satisfy the output contract before
the deterministic scenario validator is applied.
