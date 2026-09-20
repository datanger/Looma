# AEP / Looma paper plan

## Working title

**Agent-Embedded Programming: Reusing Frontier Host Agents in Ordinary Program Control Flow**

Subtitle candidate:

**Looma: A Durable Runtime for Contract-Guarded Host-Native Agent Execution**

## Central thesis

Traditional agent applications typically reconstruct agent intelligence inside the application: model clients, agent loops, tool binding, routing, state, retries, and workflow-specific orchestration. Agent-Embedded Programming (AEP) takes a different approach: an ordinary program reuses the already-running Host Coding Agent as a semantic computation unit.

AEP constrains the interface, not the internal reasoning trajectory.

```text
Program owns control flow and acceptance criteria
Agent owns semantic reasoning and evidence acquisition
Runtime owns continuity
```

The expected engineering consequence is less application-specific agent infrastructure, while the expected behavioral consequence is stronger local autonomy inside explicit program boundaries.

## Core design principles

1. **Host Capability Inheritance** — applications reuse the reasoning, planning, tool-use, and native subagent capabilities of the Host instead of rebuilding them.
2. **Bounded Autonomy** — the Host is free to choose its reasoning/tool trajectory inside an explicit semantic task boundary. This is a programming boundary, not a security sandbox; actual tool permissions remain Host-controlled.
3. **Contract-Guarded Execution** — Task, Result, Resume, and application Acceptance contracts guard the non-deterministic Agent boundary.
4. **Durable Continuity** — suspend, durable state, replay, and resume preserve ordinary Python control flow across Host execution.

## Research questions

### RQ1 — Development effort

Does AEP reduce application-specific agent orchestration and infrastructure code compared with conventional agent programming approaches?

Primary metrics:

- orchestration SLOC;
- agent-infrastructure SLOC;
- total implementation SLOC;
- number of implementation files;
- framework-specific constructs;
- configuration items;
- code changes required when the execution environment changes.

A direct claim about **developer time** requires a prospective timed implementation study or user study. SLOC alone is treated as an implementation-effort proxy, not proof of elapsed development time.

### RQ2 — Bounded autonomy

Can AEP solve perturbed tasks without changing application control-flow code by allowing the Host to adapt its internal reasoning/tool path?

Perturbations:

- primary tool unavailable;
- one source conflicts with another;
- expected file/source missing;
- first attempted strategy fails;
- additional verification is needed;
- independent subproblems can be parallelized.

Metrics:

- adaptive task success rate;
- human intervention count;
- application code modifications;
- tool-path diversity;
- contract rejection/retry count.

Two evaluation modes are required:

1. **Controlled mode:** same model, same allowed tools, same budget.
2. **Host-native mode:** the real Host may use its native environment and tools.

The second mode evaluates practical capability inheritance, not a pure causal comparison of orchestration alone.

### RQ3 — Task effectiveness and capability inheritance

Does AEP preserve task quality under controlled conditions, and can an unchanged AEP application benefit from stronger Host Agents in practical deployment?

Primary workloads:

- agentic retrieval: A-RAG / MuSiQue, HotpotQA, 2WikiMultiHopQA;
- SOTIF / regulatory analysis benchmark;
- stock-analysis Agent as a reproducible engineering case study, but not the primary quality benchmark because live web data changes over time.

Metrics depend on workload:

- exact match / F1 / answer accuracy;
- evidence recall / citation correctness;
- unsupported-claim rate;
- task success rate;
- acceptance-gate pass rate.

For Host portability/capability experiments, the same Workflow source must remain unchanged and the Host/model/version must be recorded.

### RQ4 — Contract-guarded reliability

Can Looma reject malformed or unsafe boundary outputs and resume correctly after a normal Agent suspension?

Fault classes:

- non-serializable/replay-inconsistent boundary input where applicable;
- missing Agent result;
- malformed result JSON;
- result-schema violation;
- wrong resume script;
- wrong resume arguments;
- extra fields in agent2script;
- replay-visible code divergence while suspended.

Metrics:

- invalid-output detection rate;
- false acceptance rate;
- valid completion rate;
- incorrect continuation count;
- duplicate side effects on normal replay after a persisted step.

Important limitation: current Looma does **not** claim exactly-once side effects if the process crashes inside a `step()` after the external side effect occurred but before the step result/state was durably persisted.

### RQ5 — Runtime overhead and scaling

What overhead does durable AEP execution add as Workflow history grows?

Independent variable:

- number of durable events: 10, 100, 1k, 10k (large points may be run separately).

Metrics:

- first-pass execution time;
- guarded resume/replay time;
- total state bytes;
- state.json bytes;
- number of event files.

The current implementation replays from the workflow entry and therefore history-length scaling must be reported rather than hidden.

### RQ6 — Host portability

Can the same AEP Workflow run under multiple Coding Agent hosts without application-level modification?

Metrics:

- Workflow code modifications;
- completion rate;
- Result Contract compliance;
- Resume Contract compliance;
- task-specific output quality;
- execution/tool traces.

## Baselines

Primary baselines should be limited to systems that represent distinct programming models:

1. **Direct SDK / hand-written agent loop**
2. **LangGraph StateGraph**
3. **Microsoft Agent Framework functional workflow**
4. **AEP / Looma**

AutoGen remains relevant related work and can be retained as a secondary historical baseline, but it is no longer the primary current Microsoft baseline because Microsoft now recommends Agent Framework for new users. AgentScope can be added if resources permit.

For controlled experiments:

```text
same model
same task
same data
same tool whitelist
same iteration/token budget
same evaluation
```

Only the programming/orchestration model should change.

## Workload design

### W1 — Adaptive evidence workflow

A synthetic but executable controlled workload:

```text
collect deterministic input
→ semantic research
→ evidence validation
→ analysis
→ acceptance gate
→ retry if needed
```

It is used for code-complexity, perturbation, and reliability comparisons.

### W2 — Agentic retrieval

Refactor A-RAG so the Host controls retrieval strategy while existing keyword/semantic/chunk retrieval capabilities remain application tools.

Purpose:

- demonstrate migration from an internal Agent controller to Host-native execution;
- measure quality and orchestration overhead;
- measure adaptation across multi-hop retrieval.

### W3 — SOTIF / regulatory iterative analysis

```text
scenario
→ analysis
→ deterministic/evaluator gate
→ feedback
→ revise
→ accept or stop
```

Purpose:

- demonstrate loops and program-owned acceptance criteria;
- evaluate evidence quality and bounded autonomy in a domain application.

### Engineering case study — Stock analysis

The existing stock-analysis Agent demonstrates real external-data fallback, evidence acquisition, validation, iterative research, and report generation. It is useful as a case study and execution trace, but dynamic public-web content makes it unsuitable as the sole reproducible quality benchmark.

## Experimental dimensions

| Dimension | Main question | Metrics |
|---|---|---|
| Development | Is less agent-specific engineering required? | SLOC, orchestration SLOC, files, constructs, config |
| Autonomy | Can the Agent adapt inside a fixed boundary? | perturbed-task success, interventions, code changes |
| Quality | Is task quality preserved or improved? | task-specific accuracy/evidence metrics |
| Reliability | Are invalid boundaries rejected? | detection, false acceptance, correct continuation |
| Runtime | What does durability cost? | latency, replay time, state size |
| Portability | Does the same app work across Hosts? | zero-change rate, completion, quality |

## Paper structure

### 1. Introduction

- Agent applications increasingly reconstruct model clients, agent loops, tools, routing, and workflows.
- Modern Coding Agents already provide reasoning, planning, tools, terminals, browsers, and sometimes native subagents.
- Research question: can ordinary programs directly reuse this existing intelligence?
- Introduce AEP and Looma.
- State the key tension: stronger local autonomy usually reduces predictability; AEP separates local autonomy from global program control using contracts and durable boundaries.
- Summarize contributions.

### 2. Background and Related Work

- Agent frameworks and multi-agent orchestration.
- Language-model programming: LMQL, DSPy, SGLang.
- Stateful/graph-based agent workflows.
- Durable workflow/replay systems.
- Position AEP as host-native reuse rather than another internal model/agent execution environment.

### 3. Agent-Embedded Programming

- computation model;
- Host / Program / Runtime responsibilities;
- Host Capability Inheritance;
- Bounded Autonomy;
- semantic boundaries;
- Task / Result / Resume / Acceptance contracts;
- ordinary Python loops and branches;
- Host-native concurrency.

A compact formalization can model a boundary as:

```text
B = (T, I, O, R, A)
```

where T is the task, I the program-provided input, O the result contract, R the resume contract, and A the deterministic acceptance criteria. The Agent may choose an internal action trajectory pi freely, but its result must satisfy O and A, and the continuation must satisfy R before the program continues.

**Current-main precision:** Looma now supports an optional user-declared `input_schema` on `agent()`. Inputs are normalized to replay-safe JSON, structurally validated before suspension, and hashed for replay consistency. Calls that omit `input_schema` retain the v0.1.4 replay fingerprint for backward compatibility. This input-contract feature is on `main` and must not be described as part of the published v0.1.4 wheel until a later release is cut.

### 4. Looma Runtime

- `@workflow`, `step()`, `agent()`;
- event history;
- suspend protocol;
- `script2agent`;
- Result Contract;
- Resume Contract;
- guarded handoff;
- same-command replay;
- run isolation;
- inspectability;
- limitations.

### 5. Experimental Methodology

- RQ1–RQ6;
- baselines;
- workload specifications;
- model/tool controls;
- repetitions and randomness;
- metrics;
- statistical tests;
- environment and versions.

### 6. Results

- development effort;
- bounded-autonomy perturbation results;
- task effectiveness;
- reliability fault injection;
- runtime scaling;
- Host portability.

### 7. Case Studies

- A-RAG migration;
- SOTIF iterative Agent;
- stock-analysis execution trace.

### 8. Discussion

- when AEP is appropriate;
- when a graph framework or direct SDK is preferable;
- security and trust boundary;
- replay limitations;
- Host dependency;
- threats to validity.

### 9. Conclusion

## Statistical protocol

Where applicable:

- deterministic settings or at least 3 repeated runs for stochastic methods;
- paired evaluation on identical task instances;
- 95% bootstrap confidence intervals for quality differences;
- McNemar test for paired binary success/correctness;
- Wilcoxon signed-rank test for paired latency/token distributions;
- report raw per-task records in addition to aggregates.

## Implementation phases

### Phase 0 — now

- freeze paper RQs and metric definitions;
- add reproducible Looma reliability fault injection;
- add replay/runtime scaling microbenchmark;
- add code-metric tool;
- keep raw results out of Git history by default.

### Phase 1

- implement W1 in Looma, Direct SDK, LangGraph, and Microsoft Agent Framework with shared business code;
- pin framework/model versions;
- collect code-complexity and controlled execution metrics.

### Phase 2

- refactor A-RAG to a Host-native AEP case;
- run public multi-hop QA benchmarks;
- collect quality, token/tool-call, and latency traces.

### Phase 3

- construct/curate SOTIF benchmark and expert evidence labels;
- run iterative-analysis experiments.

### Phase 4

- multi-Host portability runs;
- statistical analysis;
- figures/tables;
- paper writing and artifact release.
