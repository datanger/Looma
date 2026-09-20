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

## Host-native execution

Run this example **from inside the already-running Coding Agent host session**. Looma must not start Codex, Claude Code, SDW, or any subagent through a CLI, SDK, API, or subprocess.

The host Agent uses its own native terminal to start the workflow:

```bash
LOOMA_STATE_DIR=/tmp/looma-multi-stage-state \\
PYTHONPATH=src \\
python examples/multi_stage_agent_workflow/workflow.py \\
  --workdir /tmp/looma-multi-stage
```

When Looma emits `script2agent`, the Python process has returned a task description to the same host Agent. The host then performs that task using its native capabilities. If the task can be split, the host may use its own subagent functionality and concurrency. Looma does not participate in that scheduling.

After the host writes `output.result_file` and produces the required `agent2script`, the command is validated and the original workflow resumes.
