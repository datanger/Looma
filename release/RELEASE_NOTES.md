# Looma v0.1.0

First public experimental release of Looma.

Looma is the Python runtime for **Agent-Embedded Programming (AEP / 智能体嵌入式编程)**.

## Highlights

- `@workflow` for resumable Python workflows.
- `step()` for replay-safe deterministic or side-effectful execution.
- `agent()` for embedding a host coding agent into ordinary Python control flow.
- Same-command replay/resume.
- `script2agent` / `agent2script` boundary protocol.
- Loop support: Agent calls can appear inside normal `for` / `while` flows.
- Bundled **Agent-Embedded Programming Skill** for Codex, Claude Code, SDW and other coding-agent hosts.
- No direct LLM API dependency inside Looma workflows.
- Python 3.10–3.13 CI coverage.

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.0/looma_runtime-0.1.0-py3-none-any.whl
```

Looma v0.1.0 is experimental. The public API and persistence format may still evolve.
