# Initial experimental results

These are engineering checkpoints, not final paper claims. Final tables require repeated runs, frozen hardware/environment metadata, statistical analysis, and the model-backed experiments.

## Phase 0 — contract reliability

The current fault-injection harness covers a valid control plus malformed/missing Agent results, schema violations, invalid resume output, and replay divergence. The first successful CI run observed:

The current `main` run after adding optional Agent Input Contracts observed:

- 9/9 scenarios behaved as expected;
- 8/8 invalid boundary cases were rejected;
- 0 false acceptances;
- the valid control completed;
- an invalid `input_schema` case failed before any `script2agent` request was emitted.

This does not establish exactly-once side effects for a crash that occurs inside a side-effecting `step()` before durable persistence.

## Phase 0 — runtime scaling checkpoint

One GitHub-hosted Python 3.12 run produced the following checkpoint:

| Durable steps before Agent boundary | Initial run | Guarded resume | state.json |
|---:|---:|---:|---:|
| 10 | 71.8 ms | 104.6 ms | ~4.9 KB |
| 100 | 312.0 ms | 110.5 ms | ~41.2 KB |
| 1000 | 8533.3 ms | 166.8 ms | ~404.8 KB |

The 1000-step first-pass cost suggests that repeated full-state persistence is a likely scalability bottleneck worth optimizing. One run is insufficient to infer an asymptotic complexity.

## Phase 1 — W1 controlled semantic fixture

CI run: `35511387807`, commit `03a27efa04400788a605b88ccec35cc2de1f8ca3`.

All four implementations completed the same five scenarios with identical fixture semantics:

| Method | Task success | Orchestration SLOC | Functions | Classes | Calls | Median process time* |
|---|---:|---:|---:|---:|---:|---:|
| Direct SDK | 5/5 | 57 | 2 | 0 | 22 | 39.8 ms |
| LangGraph | 5/5 | 101 | 10 | 1 | 39 | 790.4 ms |
| Microsoft Agent Framework | 5/5 | 70 | 3 | 0 | 28 | 243.8 ms |
| Looma | 5/5 | 57 | 2 | 0 | 18 | 515.7 ms |

\*The timing is a single fixture-mode CI run and includes Python/framework startup. Looma additionally performs process suspension, guarded handoff, same-command replay, and multiple process launches. These numbers therefore measure fixture orchestration overhead, not real Agent end-to-end latency, and must not be used as a final performance ranking.

Looma's benchmark-only `host_driver.py` is excluded from application SLOC because a real AEP application relies on the already-running Host Agent; the driver only deterministically simulates that Host in CI.

## What these checkpoints support

They currently support only narrow statements:

- the four W1 implementations are behaviorally equivalent under the deterministic semantic fixture;
- the Looma application expresses the W1 control flow with substantially fewer framework-specific constructs than the LangGraph implementation in this benchmark;
- Looma pays measurable suspend/replay/process overhead that must be reported rather than hidden;
- Looma's current boundary guards reject the tested invalid outputs.

They do **not** yet support claims that Looma has higher Agent output quality, lower real-world end-to-end latency, or shorter human development time.

## RQ2 — bounded-autonomy perturbation sanity

Originally CI run `35512526131`, commit `c61fdd33da3a7f2291870970759cc9b0b5162d34`
(six scenarios).

The suite has since been extended to seven scenarios and split into a published
**development split** (3) and a **held-out split** (4); the held-out split contains a
control scenario whose correct answer is "insufficient evidence" and which requires no
discovery. Local run on Python 3.10.12, commit `38b5e14`:

| Diagnostic policy | Success |
|---|---:|
| Predefined static route | 2 / 7 (28.57%) |
| Adaptive oracle | 7 / 7 (100%) |

This is **not** an Agent-quality result. The adaptive oracle is deterministic
benchmark code, not a Host Agent. The result only verifies that the perturbation
suite is discriminative: some tasks require changing the internal evidence path
while the task interface and acceptance criteria remain unchanged.

### Gate feedback no longer leaks the oracle

The acceptance gate previously reported `problems` such as *"decision mismatch: expected
X"* and oracle source ids. Those problems are fed back to the Agent on a retry, so the
gate was handing over the answer. `validator.py` now separates the two roles:

* `validate_result(scenario_id, result)` — the feedback-safe acceptance gate, restricted
  to publicly derivable facts;
* `score_result(scenario_id, result)` — the experiment-side scorer that knows
  `expected_decision` / `expected_supporting_source_ids`.

`sanity.py` reports `gate_feedback_leaks_oracle` (currently `false`) and
`tests/test_bounded_autonomy.py` pins both the separation and the non-leak.

## RQ2 — controlled four-paradigm perturbation comparison

> **Admissibility notice (2026-09-21).** Every task instance in this section comes from
> `experiments/workloads/bounded_autonomy/scenarios.json`, a suite **we authored**. Under
> the rule that all reported task data must come from a recognised public benchmark, these
> numbers are **not admissible as paper evidence** and must not appear in a results table.
> The *harness* built here is reusable and its findings (route ownership, the closed
> gate-leak, the widening ablation design) carry over; the numbers do not. The public-data
> re-basing is `research/RETRIEVAL_PERTURBATION_PROTOCOL.md`.

New experiment: `experiments/workloads/bounded_autonomy/controlled/`.

Every paradigm runs the *same* deterministic driver policy (a model stand-in with no
oracle access), the *same* seven scenarios, and the *same* budget (3 rounds × 12 actions
per round). The single difference is **who owns the tool route**. Each conventional
paradigm is run twice: `dev` = the route set an author freezes after the development
split, `widened` = the route set the held-out split turns out to require.

Local run: Python 3.10.12, platform `Linux-6.8.0-138-generic`, commit `38b5e14`,
worktree dirty. Command:

```bash
PYTHONPATH=$PWD:$PWD/src python -m experiments.workloads.bounded_autonomy.controlled.run_controlled \
  --output experiments/results/rq2-controlled.json
```

| Implementation | Batch | ATSR dev | ATSR eval | eval route gaps | Application SLOC | Route-delta SLOC | Mean actions |
|---|---|---:|---:|---:|---:|---:|---:|
| Direct SDK | dev | 1.00 | **0.25** | 4 (all `list`) | 92 | 0 | 3.00 |
| Direct SDK | widened | 1.00 | 1.00 | 0 | 101 | +9 | 3.43 |
| LangGraph | dev | — | — | — | 189 | 0 | — |
| LangGraph | widened | — | — | — | 200 | +11 | — |
| Microsoft Agent Framework | dev | — | — | — | 114 | 0 | — |
| Microsoft Agent Framework | widened | — | — | — | 118 | +4 | — |
| AEP / Looma | dev | 1.00 | **1.00** | 0 | 110 | 0 | 3.43 |
| AEP / Looma | widened | 1.00 | 1.00 | 0 | 110 | 0 | 3.43 |

Reading of the Looma row: `declared_routes` is empty
(`application_declared_actions == []`), the Host supplies `read` + `list` in **both**
batches, and `looma/workflow.py` is byte-identical across them (SHA-256 recorded in the
result JSON). `host_driver.py` simulates the external Host, is excluded from application
SLOC, and is reported separately (`host_driver_sloc = 115`). Looma's AEP application also
SLOC-counts higher than the direct-SDK loop (110 vs 92); the claim here is route
stability, not smaller code.

**The LangGraph and Microsoft Agent Framework numbers are not yet measured.** Both need
pinned dependencies (`experiments/requirements-phase1.txt`:
`langgraph==1.2.11`, `agent-framework-core==1.19.0`) that are unavailable on this machine,
so their rows are recorded as `dependency_missing: true`; only their SLOC columns come
from local static counting. Their behavioral rows must come from the
`controlled-comparison` CI job, which installs those pins and uploads
`research-results/rq2-controlled.json`.

What this supports and what it does not:

* **Supports**: with orchestration, driver and budget held fixed, an application that owns
  its route set fails 3 of 4 held-out scenarios with a `RouteMissing` on `list` and must be
  edited (+9 SLOC) to recover, while the AEP application is unchanged and scores 4/4
  because the Host owns the route set.
* **Does not support**: any claim about Agent output quality. The driver is a deterministic
  policy, not a model, and no LLM was involved. Quality claims still require the
  model-backed runs described below.
* The held-out discriminator is essentially the single mechanism "can the orchestration
  discover an unadvertised source"; unavailability/conflict axes appear only in the
  development split, and the retry dimension is barely exercised (`rounds == 1` everywhere).

The paper-quality RQ2 experiment must still run the unchanged
`experiments/workloads/bounded_autonomy/workflow.py` under real Host Agents and
compare it with model-controlled dynamic Agent/workflow baselines.

## RQ2 re-based on public data — retrieval perturbation

New workload: `experiments/workloads/retrieval_perturbation/`. Protocol:
`research/RETRIEVAL_PERTURBATION_PROTOCOL.md`.

The same RQ2 question is asked again on **public multi-hop QA instances only**. Task
instances and gold labels come from the pinned A-RAG revision
(`b9198a5a8702cc35c6df7542529357a9af95d928`: MuSiQue, HotpotQA, 2WikiMultiHopQA); the six
perturbations are deterministic transforms over that public corpus and the public tool
surface, and no question, answer or paragraph is authored by us.

Conditions: development split = `baseline`, `primary_tool_unavailable`; held-out split =
`source_id_renamed`, `snippet_only`, `evidence_withheld` (negative control),
`distractor_chunk`. The frozen development route set is
`semantic_search, keyword_search, read_chunk`; the held-out split additionally needs
`list_chunks`, because once the corpus is re-keyed nothing in the frozen set can turn an
opaque handle into a chunk id.

**Status of this experiment: control flow verified, public numbers pending.**

Verified locally on the fixture corpus (Python 3.10.12, no network, no framework
dependencies) by `tests/test_retrieval_perturbation.py` (13 tests) and by running the
runner end to end. The fixture run is labelled `mode: "fixture"`, carries a
`fixture_warning`, and **its numbers are control-flow checks, not results** — they are
deliberately not reproduced in this document.

What the fixture run does establish, because these are structural properties rather than
measurements:

* the frozen development route set genuinely fails on the held-out split
  (`eval_route_gaps > 0`, one `RouteMissing` on `list_chunks` per re-keyed instance);
* adding that single route removes every held-out route gap and raises held-out adaptive
  success;
* the AEP application declares **no** route at all, is byte-identical across both batches
  (`application_sha256` equal, `route_declaration_delta_sloc == 0`) and needs no widening
  edit, whereas the direct-SDK application's hash and SLOC both change;
* for every perturbation, the set of visible chunk texts is a **subset** of the public
  corpus — no transform introduces text;
* the instance payload handed to a paradigm carries no gold label, no gold evidence ids and
  no original-id mapping;
* the boundary gate cannot see the gold answer (it takes exactly two arguments, result and
  persisted session), still reports the agent's own bad citation back to it, and
  `--expect-public` refuses to emit a result from a fixture corpus.

The public numbers come from the `public-perturbation-comparison` job in
`.github/workflows/research-retrieval-perturbation.yml`, which downloads the pinned data,
runs all three datasets with `--expect-public`, and uploads
`rq2-retrieval-perturbation.json`. No row of that table is to be filled in before it runs.

Two limits must travel with any table from this workload:

1. **Answer quality is not measured.** The deterministic retrieval driver cannot reason
   across hops, so contain-match and EM from this runner are meaningless. The measured
   quantity is whether the public gold evidence stays *reachable* under perturbation.
2. **Evidence presence is a proxy where the public record allows no exact ids.** A chunk
   counts as gold evidence iff the normalized gold answer occurs in its text; that
   over-counts. Exact-id recall is used whenever the public question record provides it.

## A-RAG host-native integration checkpoint

The A-RAG case study installs the unmodified `datanger/arag` commit
`a44de6b2216bf6791979c4b6ac4ae106212fa1a6` and bypasses its internal
`BaseAgent` / `LLMClient` while reusing the original `ToolRegistry`,
`keyword_search`, `semantic_search`, `read_chunk`, and `AgentContext`.

CI run `35511770105` successfully exercised:

- unmodified A-RAG keyword retrieval;
- unmodified A-RAG chunk reading;
- persisted retrieval context;
- Looma suspension and guarded handoff;
- result-schema validation;
- deterministic verification that cited chunks were actually read;
- same-command replay and completion.

This is an integration result, not yet a MuSiQue/HotpotQA/2Wiki quality result.

The benchmark utilities now also support deterministic subset freezing, run
manifests with content hashes, paired bootstrap intervals, and exact McNemar
tests for paired Contain-Match correctness.

## Frozen public A-RAG development data

CI run `35512896077`, commit
`f8f6f08aa921bcf1b8efe7bf69ca6a0223a7a5b7`, successfully downloaded the
public A-RAG benchmark repository at upstream revision
`b9198a5a8702cc35c6df7542529357a9af95d928` and froze deterministic 100-item
development subsets for all three primary datasets.

| Dataset | Questions SHA-256 | Chunks SHA-256 | dev100 SHA-256 |
|---|---|---|---|
| MuSiQue | `42dfd487...` | `41d439ad...` | `5bd8b7a9...` |
| HotpotQA | `ecc641d5...` | `cb76f6fd...` | `0255f230...` |
| 2WikiMultiHopQA | `246e43fb...` | `e92b8bcf...` | `b94b2904...` |

The exact full hashes and selected question ids are stored in the generated
`manifest.json`. This freezes the first real A-RAG development evaluation set;
no answer-quality comparison has been run yet.
