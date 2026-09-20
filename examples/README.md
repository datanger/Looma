# Looma examples

These examples are small, reusable **Agent-Embedded Programming (AEP)** patterns rather than toy API snippets.

They show how ordinary Python keeps control of branching, loops, retries, batch processing, validation, and termination while a host Coding Agent supplies semantic reasoning at `agent()` boundaries.

| Example | Programming pattern | What the Agent does |
|---|---|---|
| `basic.py` | single Agent call | make one structured decision |
| `branching.py` | `if / elif / else` | choose the next deterministic branch |
| `loop.py` | bounded `for` loop | decide whether to stop and provide the next value |
| `while_retry.py` | `while` + retry | inspect deterministic validation failures and propose the next candidate |
| `code_repair.py` | test → repair → test loop | inspect test failures and modify the repository using host tools |
| `batch_review.py` | batch processing | review each deterministic record and return a structured verdict |
| `generate_validate.py` | Agent output + deterministic validator | create/update an artifact until programmatic validation passes |
| `multi_script_workflow/` | multiple standalone scripts | orchestrate `collect.py → transform.py → agent → report.py` as one resumable workflow |
| `multi_stage_agent_workflow/` | multi-stage Agent/Script workflow | `prepare.py → Agent → analyze.py → Agent → gate.py → summary/detailed report` |

## How to run

Install Looma first:

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.2/looma_runtime-0.1.2-py3-none-any.whl
```

Then run an example normally:

```bash
python examples/branching.py
```

When an example reaches `agent()`, Looma emits `script2agent` and exits with code `75`. The host Coding Agent should complete the task, write `output.result_file`, return the expected `agent2script`, and resume through the guarded handoff path.

These examples intentionally keep business logic small so the control-flow pattern is easy to reuse in real projects.

## Multi-script workflow

`multi_script_workflow/` demonstrates how Looma can orchestrate an existing script-based pipeline without merging all logic into one Python file:

```text
collect.py
   ↓
transform.py
   ↓
agent(...)
   ↓
report.py
```

The outer `workflow.py` owns orchestration. Each standalone script runs through `step()`, so scripts completed before an Agent suspension are replayed from history instead of being executed again.

```bash
python examples/multi_script_workflow/workflow.py \
  --workdir /tmp/looma-multi-script
```

## Multi-stage Agent/Script workflow

`multi_stage_agent_workflow/` demonstrates two Agent boundaries and a final deterministic branch:

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

The repository includes an automated integration test that performs both suspend/resume cycles and verifies each external script executes exactly once.

Run the multi-stage example from inside the already-running Coding Agent host session:

```bash
LOOMA_STATE_DIR=/tmp/looma-multi-stage-state \
PYTHONPATH=src \
python examples/multi_stage_agent_workflow/workflow.py \
  --workdir /tmp/looma-multi-stage
```

When the workflow reaches an Agent boundary, control returns to the same host Agent. The host uses its native reasoning, tools and optional subagents, writes the structured result, validates the Resume Contract through `looma handoff`, and continues the original workflow. Looma never launches Codex or another Agent process.
