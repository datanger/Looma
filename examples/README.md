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

## How to run

Install Looma first:

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.1/looma_runtime-0.1.1-py3-none-any.whl
```

Then run an example normally:

```bash
python examples/branching.py
```

When an example reaches `agent()`, Looma emits `script2agent` and exits with code `75`. The host Coding Agent should complete the task, write `output.result_file`, return the expected `agent2script`, and resume through the guarded handoff path.

These examples intentionally keep business logic small so the control-flow pattern is easy to reuse in real projects.
