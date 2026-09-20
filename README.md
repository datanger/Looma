# Looma

**Weave coding agents into ordinary Python control flow.**

Looma is a replay-based Python runtime for composing deterministic Python code with host coding agents such as Codex, Claude Code, and SDW.

It keeps the `script2agent -> agent2script -> script` contract while exposing a natural Python API:

```python
from looma import workflow, step, agent

@workflow
def process(data):
    parsed = step(preprocess, data)
    decision = agent(
        task="Analyze the input and decide the next action.",
        input=parsed,
        output_schema=dict,
    )
    return step(run, decision)
```

Looma does not call an LLM API directly. The host coding agent provides model access, session management, reasoning, and tool permissions. Looma provides suspend, state persistence, replay, resume, and the Agent/Script boundary protocol.

## Core runtime

```text
Python command
    ↓
@workflow
    ↓
step()
    ↓
agent()
    ↓
script2agent
    ↓
host coding agent
    ↓
agent2script
    ↓
same Python command
    ↓
replay/resume
```

The project is under active development.
