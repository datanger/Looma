# W1: Adaptive Evidence Workflow

This is the first controlled workload for comparing AEP with conventional agent-programming approaches.

## Functional requirements

Every implementation must satisfy the same externally visible behavior:

1. Load a deterministic task input.
2. Perform a semantic evidence-gathering stage.
3. Validate the returned evidence with deterministic code.
4. Perform a semantic analysis stage.
5. Validate the analysis with deterministic code.
6. Retry a bounded number of times if evidence or analysis is insufficient.
7. Produce one JSON artifact with a deterministic top-level status:
   - `complete`
   - `insufficient_evidence`
8. Do not repeat already-persisted deterministic side effects during a normal resume/replay.

## Controlled perturbations

The harness will provide semantically equivalent task instances where:

- the preferred evidence source is unavailable;
- sources disagree;
- one expected file is absent;
- the first strategy cannot satisfy the evidence gate;
- an additional verification step is required.

## Fair-comparison rules

- shared business functions are identical across implementations;
- same model;
- same tool whitelist;
- same prompt/task information;
- same retry/iteration budget;
- same evidence corpus;
- same final validators.

Only orchestration/programming model code belongs in each baseline directory and is counted as orchestration SLOC.

## Planned implementations

```text
adaptive_evidence/
├── shared/
├── direct_sdk/
├── langgraph/
├── microsoft_agent_framework/
└── looma/
```

Phase-1 fixture implementations are now populated. LangGraph is pinned to 1.2.11 and Microsoft Agent Framework Core to 1.19.0 for the controlled orchestration run. The deterministic semantic fixture isolates orchestration equivalence; it is not used to claim comparative LLM quality.
