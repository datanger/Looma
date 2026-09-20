# Looma design

## Objective

Looma provides an ordinary-looking Python programming model while retaining the `script2agent` / `agent2script` boundary protocol underneath.

The key developer experience is:

```python
@workflow
def process(data):
    prepared = step(prepare, data)
    decision = agent(task="decide", input=prepared, output_schema=dict)
    return step(apply, decision)
```

The function looks synchronous, but an `agent()` call may terminate the current process and continue logically after the original command is run again.

## Replay instead of source-code splicing

Looma does not splice the upper and lower halves of a Python function and does not serialize a raw Python call stack. It records durable events and restarts the original script.

During replay:

- `step()` returns a previously persisted result;
- a completed `agent()` returns the persisted Agent result;
- a waiting `agent()` re-emits the same `script2agent` request;
- ordinary Python control flow executes again.

This preserves normal `if`, `for`, `while`, function calls and exceptions without requiring an AST compiler in V0.1.

## Data plane and control plane

```text
Data plane
    script2agent <-> agent2script

Control plane
    run -> event -> suspend -> persist -> same command -> replay -> continue
```

The Skill defines the boundary contract. Looma Runtime owns the control plane.

## Same-command resume

At workflow entry Looma captures:

```text
sys.executable
sys.argv
cwd
```

The generated `script2agent.expected_output` uses the same executable and arguments. The Agent therefore returns the original command as `agent2script`; workflow ids and resume ids remain private to Looma.

## Durable state

Default state lives under `.looma/` and contains:

- an invocation-to-active-run pointer;
- workflow state;
- ordered events;
- cached `step()` results;
- generated `script2agent` requests;
- Agent result files.

A process may exit completely between Agent calls. The next same-command invocation reconstructs logical execution by replaying persisted history.

## Determinism contract

Replay-visible call order is part of workflow history. Every event records:

- event index;
- event kind (`step` / `agent`);
- call-site key;
- input hash;
- result/request path;
- status.

A mismatch raises `ReplayMismatchError` rather than continuing from an ambiguous state.

## Why `step()` exists

Replay re-executes ordinary Python. Therefore replay-unsafe operations must be converted into durable events. `step(fn, *args, **kwargs)` runs `fn` once, persists its JSON-compatible result and returns the saved result on replay.

## Host-agent boundary

Looma intentionally does not own a model client. A coding-agent host such as Codex, Claude Code or SDW is responsible for reasoning and tool execution. The host receives `script2agent`, writes the requested business result JSON and finally emits the expected `agent2script` command.

This separation lets Looma remain model-agnostic and preserves the existing programmatic-coding Skill contract.
