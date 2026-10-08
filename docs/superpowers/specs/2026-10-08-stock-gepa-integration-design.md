# Stock Analysis GEPA Integration Design

## Goal

Make `examples/stock_analysis_agent` demonstrate the complete AEP + GEPA-style
loop while preserving its existing sourced-market-data, recent-news, evidence
gate, analysis validation, and deterministic report rendering behavior.

## Scope

The integration optimizes one textual candidate component,
`analysis_instruction`. The candidate is injected into the existing final
analysis Agent task. Python owns candidate state, validation, budget, and
acceptance; the current Host Agent proposes candidate mutations through the
existing `request_reflection()` boundary.

The market acquisition and news-research boundaries remain unchanged. GEPA is
used only when an analysis result is structurally valid but fails the
deterministic analysis acceptance gate. A proposal is evaluated by running the
same analysis task with the proposed instruction and validating the result.
The existing final evidence re-check and report status remain authoritative.

## Data flow

```text
market/news evidence
        ↓
analysis candidate + agent analysis
        ↓
validate_analysis.py
        ├─ ready → existing final evidence gate → render
        └─ revise → request_reflection(candidate, validation feedback)
                         ↓
                 proposed candidate + agent analysis
                         ↓
                 deterministic acceptance gate
                         ↓
                 continue / complete / insufficient_evidence
```

The optimization state uses `OptimizationState`, `select_candidate()`,
`EvaluationBatch`, `request_reflection()`, and `accept_proposal()` directly.
No model client, Agent launcher, new runtime primitive, or hidden retry loop is
introduced.

## Testing

The stock integration test will exercise a complete fixture-backed host flow:

1. AKShare fallback and sourced market data handoff;
2. recent-news handoff and evidence validation;
3. an invalid-but-schema-valid analysis result;
4. GEPA reflection and a second analysis Agent boundary;
5. deterministic proposal acceptance and final report rendering;
6. replayed `step()` events and completed durable run state.

The test will assert the GEPA task payload, candidate proposal result,
frontier/optimization state, final report, and event ordering.
