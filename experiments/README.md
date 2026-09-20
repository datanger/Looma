# AEP / Looma research experiments

This directory contains reproducible experiment harnesses for the AEP/Looma paper.

The experiment design is defined in [../research/PAPER_PLAN.md](../research/PAPER_PLAN.md).

## Phase-0 experiments

### Contract fault injection

```bash
python -m experiments.reliability_faults \
  --output experiments/results/reliability.json
```

The benchmark injects malformed/missing Agent results, invalid resume outputs, and replay-visible code divergence. A valid control case is included.

The benchmark evaluates the contracts Looma currently implements. It does **not** claim exactly-once execution if a process dies inside a side-effecting `step()` before its result has been durably recorded.

### Runtime scaling

Quick run:

```bash
python -m experiments.runtime_scaling \
  --events 10,100,1000 \
  --repeats 3 \
  --output experiments/results/runtime-scaling.json
```

A larger 10k-event point should be run separately because current state persistence/replay may make it substantially slower:

```bash
python -m experiments.runtime_scaling \
  --events 10000 \
  --repeats 3 \
  --output experiments/results/runtime-scaling-10k.json
```

Agent output is deterministic in this microbenchmark. This isolates Looma process/state/replay overhead from model inference latency.

### Code metrics

Use functionally equivalent implementations with shared business logic kept outside each framework-specific implementation directory.

```bash
python -m experiments.code_metrics \
  looma=experiments/workloads/adaptive_evidence/looma \
  direct=experiments/workloads/adaptive_evidence/direct_sdk \
  langgraph=experiments/workloads/adaptive_evidence/langgraph \
  autogen=experiments/workloads/adaptive_evidence/autogen \
  --output experiments/results/code-metrics.json
```

Those baseline directories will be added in Phase 1 after the workload specification and framework versions are frozen.

## Raw results

`experiments/results/` is ignored by Git by default. Paper tables should be generated from immutable raw run records whose environment, versions, commit SHA, model/Host, and random settings are recorded.
