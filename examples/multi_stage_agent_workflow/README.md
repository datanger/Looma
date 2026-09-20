# Multi-stage Agent/Script workflow

This example demonstrates a workflow with **multiple standalone scripts and two Agent boundaries**:

```text
prepare.py
   ↓
Agent #1
   ↓
analyze.py
   ↓
Agent #2
   ↓
gate.py
   ↓
if / else
 ├─ summary_report.py
 └─ detailed_report.py
```

The workflow intentionally suspends twice. On every resume, Looma replays completed `step()` events instead of re-running the already completed scripts.

Run the workflow directly:

```bash
LOOMA_STATE_DIR=/tmp/looma-multi-stage-state \
python examples/multi_stage_agent_workflow/workflow.py \
  --workdir /tmp/looma-multi-stage
```

For a real Codex-hosted end-to-end run, use:

```bash
python examples/multi_stage_agent_workflow/run_with_codex.py
```

That helper starts a single `codex exec --sandbox workspace-write` session and instructs Codex to act as the Looma host: run the workflow, consume each `script2agent`, write the business result, return exactly `expected_output`, pass it through `looma handoff`, and continue until the workflow exits successfully.

The default work directory is repo-local `.looma-codex-e2e/` so it remains writable under Codex's workspace-write sandbox. The runner uses `PYTHONPATH=src`, so an editable install is not required for this repository-level E2E test.

No LLM API client is embedded in the workflow itself; Codex remains the external host Agent.
