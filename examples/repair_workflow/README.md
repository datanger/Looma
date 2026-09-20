# Host-native code repair workflow

This example repairs a small broken Python project until its tests pass.

It intentionally combines the main Looma/AEP features in one workflow:

```text
prepare_workspace.py
        ↓
    run_checks.py
        ↓
      passed? ─────────────── yes ─→ build_report.py
        │
        no
        ↓
      agent(...)
        ↓
Current Host Coding Agent
        ├─ root-cause analysis subagent
        ├─ test-contract review subagent
        └─ regression-risk review subagent
                 ↓
              gather
                 ↓
       Host edits project files
                 ↓
            replay/resume
                 ↓
              loop
```

The Python workflow owns the loop and termination condition. Looma only returns the repair task to the **already-running host Agent**.

If the host supports native subagents, the task explicitly asks it to run three independent analysis tracks concurrently. Looma does not start those subagents itself and does not call any Agent CLI, SDK, or model API.

## What gets repaired

`template/` contains a deliberately broken mini project:

- `calculator.divide()` uses floor division instead of true division;
- `calculator.clamp()` has incorrect bounds logic;
- `test_calculator.py` expresses the intended behavior.

`prepare_workspace.py` copies that template into the requested work directory so the example source remains unchanged.

## Run

Run this **from inside the current Coding Agent host session**:

```bash
PYTHONPATH=src \
LOOMA_STATE_DIR=/tmp/looma-repair-state \
python examples/repair_workflow/workflow.py \
  --workdir /tmp/looma-repair-demo
```

Execution is:

1. `prepare_workspace.py` creates the repair workspace.
2. `run_checks.py` executes the project tests.
3. If tests fail, `agent(...)` returns a repair task to the current host.
4. The host analyzes the failures, optionally uses native subagents concurrently, edits the workspace, writes the structured Agent result, and resumes through Looma handoff.
5. The Python `for` loop runs checks again.
6. When tests pass, `build_report.py` writes the final report.

The workflow supports multiple repair rounds. Completed scripts are durable `step()` events, so process replay does not re-run earlier completed steps.

## Host responsibility at an Agent boundary

The emitted task asks the host to use three independent analysis tracks when native subagents are available:

```text
root-cause analysis
test-contract review
regression-risk review
```

Those may run concurrently inside the host. After gathering the analysis, the main host Agent edits the project and returns one structured result.

If the host has no subagent capability, the same task can be performed serially. Workflow correctness does not depend on concurrency.
