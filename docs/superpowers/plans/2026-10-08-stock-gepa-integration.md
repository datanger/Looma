# Stock Analysis GEPA Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the existing GEPA-style candidate/reflection protocol into the stock-analysis example and prove it through a complete suspend/resume integration test.

**Architecture:** Keep market acquisition, news research, evidence validation, and report rendering unchanged. Add a stock-specific `analysis_instruction` candidate around the final analysis Agent call; deterministic validation becomes the candidate evaluation evidence, and `request_reflection()` plus `accept_proposal()` manage one or more strategy revisions.

**Tech Stack:** Python 3.10+, Looma AEP runtime, dataclasses, existing JSON subprocess validators, pytest subprocess integration tests.

---

### Task 1: Extend the stock integration test with a GEPA reflection boundary

**Files:**
- Modify: `tests/test_stock_analysis_agent.py:207-351`

- [ ] **Step 1: Change the first analysis fixture to be schema-valid but fail the deterministic validator without requesting more research.**

Set `needs_more_research` to `False`, keep the four analysis tracks, and make `market_evidence` empty. Assert that the next request is a GEPA reflection task containing `CandidateProposal`-relevant strategy language and the validation failure.

- [ ] **Step 2: Run the focused test and verify it fails at the new reflection request.**

Run: `PYTHONPATH=src /home/ki-zj-2551/work/Code/QuantStrategy/.pixi/envs/sequence-ml/bin/python -m pytest -q tests/test_stock_analysis_agent.py::test_stock_analysis_agent_host_fallback_and_research_loop`

Expected: FAIL because the current stock workflow has no GEPA reflection request after a failed analysis validation.

- [ ] **Step 3: Add a candidate proposal fixture and assertions for the proposal-analysis resume.**

The proposal must be:

```json
{
  "candidate": {
    "analysis_instruction": "Cite concrete market observations and explicitly state counter-evidence."
  },
  "components_to_update": ["analysis_instruction"]
}
```

After resuming with this proposal, assert a new analysis request carrying the proposed strategy, then resume with a ready analysis and assert the final report is complete.

- [ ] **Step 4: Run the focused test again and confirm it still fails only because production code has not implemented the new path.**

Run the same focused pytest command. Expected: FAIL at the missing strategy/reflection event rather than at test setup.

### Task 2: Add the stock-specific candidate evaluation and reflection loop

**Files:**
- Modify: `examples/stock_analysis_agent/workflow.py:17-20,315-396`
- Modify: `examples/stock_analysis_agent/README.md:30-49`

- [ ] **Step 1: Add the optimization imports and the default strategy candidate.**

Add:

```python
from looma.optimization import EvaluationBatch, OptimizationState, candidate_id, select_candidate
from looma.optimization.engine import request_reflection
from looma.optimization.state import accept_proposal

DEFAULT_ANALYSIS_INSTRUCTION = (
    "Cite concrete market observations and explicitly state counter-evidence."
)
```

Initialize an `OptimizationState` immediately before the existing analysis loop with the single `analysis_instruction` component and a bounded iteration budget derived from `max_research_rounds`.

- [ ] **Step 2: Add deterministic conversion from validation output to `EvaluationBatch`.**

Create a small pure helper that gives a higher-is-better score of `1.0` when `validate_analysis.py` returns `ready`, otherwise `0.0`, and stores the validation problems plus the analysis output in `side_information`. Set `metric_calls=1` for each evaluated analysis result.

- [ ] **Step 3: Include the selected candidate in the existing final-analysis task and input.**

Append the candidate instruction to the task as a bounded strategy hint and add `analysis_strategy` to the Agent input. Do not move evidence acquisition or allow the Agent to decide report status.

- [ ] **Step 4: On a deterministic analysis-validation failure, request and evaluate a proposal.**

When `needs_more_research` is false but validation is not ready:

1. Build the parent `EvaluationBatch`.
2. Call `request_reflection()` with `components_to_update=["analysis_instruction"]`, current frontier IDs, validation side information, and the remaining optimization budget.
3. Run the same final-analysis Agent task with `proposal.candidate`.
4. Validate the proposed analysis with the existing `step(run_json_script, validate_analysis.py, ...)` gate.
5. Build the proposal evaluation and call `step(accept_proposal, ...)` with the parent candidate ID.
6. Restore the returned state through `OptimizationState.from_json()` and continue or finish based on the deterministic result.

Do not pass Python callables as step arguments; the stock path must keep all replay-visible values JSON-compatible.

- [ ] **Step 5: Preserve the existing research-supplement path.**

If either analysis says `needs_more_research=true`, keep the current targeted research behavior and do not treat the Agent self-declaration as acceptance. The final evidence check and `report_status` calculation remain unchanged.

- [ ] **Step 6: Update the stock README diagram and prose.**

Document that the final analysis stage now has a deterministic validation failure branch into GEPA-style candidate reflection, proposal evaluation, and acceptance before report rendering.

### Task 3: Verify the integrated behavior and package hygiene

**Files:**
- Test: `tests/test_stock_analysis_agent.py`
- Test: `tests/test_examples.py`

- [ ] **Step 1: Run the focused stock integration test.**

Run: `PYTHONPATH=src /home/ki-zj-2551/work/Code/QuantStrategy/.pixi/envs/sequence-ml/bin/python -m pytest -q tests/test_stock_analysis_agent.py`

Expected: PASS, including the GEPA reflection event, accepted candidate, replayed steps, and completed report.

- [ ] **Step 2: Run all optimization and stock regression tests.**

Run: `PYTHONPATH=src /home/ki-zj-2551/work/Code/QuantStrategy/.pixi/envs/sequence-ml/bin/python -m pytest -q tests/test_optimization_*.py tests/test_gepa_example.py tests/test_stock_analysis_agent.py tests/test_examples.py`

Expected: PASS with zero failures.

- [ ] **Step 3: Compile every example and inspect the working tree.**

Run: `PYTHONPATH=src /home/ki-zj-2551/work/Code/QuantStrategy/.pixi/envs/sequence-ml/bin/python -m pytest -q tests/test_examples.py && git status --short`

Expected: example compilation passes and only the intended stock integration, README, spec, and plan files are changed.
