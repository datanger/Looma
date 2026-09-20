# Looma design

## Objective

Looma is a Python implementation of **Agent-Embedded Programming (AEP)**.

The key programming model is ordinary Python:

```python
@workflow
def process(data):
    prepared = step(prepare, data)
    decision = agent(task="decide", input=prepared, output_schema=dict)
    return step(apply, decision)
```

The function looks synchronous, but an `agent()` boundary may terminate the current Python process. The already-running Coding Agent host completes the task, then the original Python command is resumed and replayed.

Looma never launches Codex, Claude Code, SDW, another Agent process, or subagents. Host-native reasoning, tools, concurrency and subagent scheduling remain owned by the host.

## AEP control handoff

The abstract execution model is:

```text
Program owns workflow control
        │
        ▼
Agent Boundary
        │
        ├── Task Contract
        ▼
Existing Coding Agent Host
        │
        ├── reasoning / tools / native subagents / concurrency
        │
        ├── Result Contract
        │
        └── Resume Contract
        ▼
Program Runtime
        │
        └── validate → replay → continue
```

Looma maps those concepts to:

```text
Agent Boundary      -> agent()
Task Contract       -> script2agent.task
Input Contract      -> agent(input_schema=...) + output.input_schema
Result Contract     -> output.result_file + output.output_schema
Resume Contract     -> expected_output
Resume validation   -> guarded agent2script
Continuation        -> same-command replay/resume
```

## Replay instead of source-code splicing

Looma does not split Python source around an Agent call and does not serialize a raw Python call stack. It records durable events and restarts the original script.

During replay:

- `step()` returns a previously persisted result;
- a completed `agent()` returns the persisted and validated Agent result;
- a waiting `agent()` re-emits the same `script2agent` request;
- ordinary Python control flow executes again.

This preserves normal `if`, `for`, `while`, function calls and exceptions without requiring an AST compiler.

## Data plane and control plane

```text
Data plane
    script2agent
    output.result_file
    agent2script

Control plane
    run -> event -> suspend -> persist -> validate -> same command -> replay -> continue
```

The bundled AEP Skill defines host behavior at the boundary. Looma Runtime owns durable program continuity.

## Same-command resume

At workflow entry Looma captures:

```text
sys.executable
sys.argv
cwd
LOOMA_RUN_KEY (optional)
```

The generated `script2agent.expected_output` uses the same executable and arguments. Workflow ids and continuation ids stay private to Looma.

Before resume, `looma handoff` requires:

```text
actual.keys   == {"script", "args"}
actual.script == expected_output.script
actual.args   == expected_output.args
```

Before suspension, a declared `input_schema` must accept the normalized Agent input. The Agent result must also exist, be valid JSON, and satisfy `output.output_schema`.

## Input and result validation

Looma can validate both sides of the semantic boundary. A caller may optionally provide `input_schema`; the normalized JSON-compatible input is validated **before** an Agent request is emitted. Invalid input raises `AgentInputValidationError`, so the workflow never suspends with a structurally invalid boundary input.

The declared input schema is also included in the replay-visible Agent fingerprint. Calls without `input_schema` preserve the v0.1.4 fingerprint for compatibility.

Looma emits structural JSON Schema for builtins and dataclass models, and preserves schema mappings or Pydantic JSON Schema supplied by callers. The same structural validator is used for declared input contracts and Agent result contracts.

The handoff validator supports the structural subset needed at the Agent boundary, including:

- object / array / string / integer / number / boolean / null;
- required properties;
- `additionalProperties`;
- array `items`;
- `enum` / `const`;
- `anyOf` / `oneOf` / `allOf`;
- local `#/$defs/...` references;
- basic length/item-count constraints.

Invalid Agent results cannot resume the expected command. Runtime replay also validates structured results as a second line of defense if the guarded handoff path is bypassed.

## Durable state

Default state lives under `.looma/` and contains:

- invocation-to-active-run pointers;
- workflow state;
- ordered events;
- cached `step()` results;
- generated `script2agent` requests;
- Agent result files.

JSON state writes use same-directory temporary files plus atomic replacement, reducing the chance that an interrupted write leaves a partially written durable-state file.

Completed and failed runs release their active invocation pointer. Historical run directories remain inspectable.

## Independent workflow instances

By default, one active run is associated with a workflow + command + working directory.

When the same command needs multiple independent logical instances, the caller can set:

```bash
LOOMA_RUN_KEY=job-a python main.py
LOOMA_RUN_KEY=job-b python main.py
```

The run key participates in the invocation fingerprint, so the two active histories are isolated. The same run key continues to identify the same logical active run.

This is instance isolation, not Agent concurrency. Agent/subagent concurrency still belongs to the host.

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

Replay re-executes ordinary Python. Therefore replay-unsafe operations must be converted into durable events.

`step(fn, *args, **kwargs)` runs `fn` once, persists its JSON-compatible result, and returns the saved result on replay.

Typical uses include file/database writes, subprocesses, tests, network calls, expensive parsing and other operations that must not be repeated after an Agent suspension.

## Host-agent boundary

Looma intentionally does not own a model client or Agent launcher.

A Coding Agent host such as Codex, Claude Code or SDW is responsible for:

- understanding `script2agent.task`;
- using its own reasoning and tools;
- optionally creating native subagents;
- deciding whether independent work should run concurrently;
- writing the structured business result;
- returning the exact resume contract.

The host may optimize execution internally, but that must not change Looma's program semantics.

## Recoverable capability fallback

External dependencies are allowed to fail without collapsing the AEP model. A deterministic `step()` can return a structured recoverable failure; the next `agent()` boundary can ask the **current host** to use its native tools to obtain sourced real evidence.

```text
step(): provider attempt
        │
        ├─ ready → deterministic processing
        └─ recoverable failure
                ↓
             agent()
                ↓
      current host native tools
                ↓
        sourced real evidence
                ↓
       step(): validate / accept
                │
                ├─ pass → continue
                └─ fail → retry / insufficient / fail
```

This does not turn Looma into an HTTP client, browser, or Agent launcher. The host still owns semantic research and tool use; the program owns the retry bound and any acceptance criteria that can be made deterministic.

Live fallbacks must not fabricate, interpolate, or synthesize missing business facts merely to satisfy a schema. Provenance should be retained when the workflow depends on externally acquired evidence. Fixtures and mocks are appropriate for deterministic CI control-flow tests, but must remain clearly separated from live workflow evidence.
## Observability

`looma status` lists local runs.

`looma inspect [run-id]` exposes:

- workflow/run status;
- invocation and optional run key;
- event history;
- pending request/result paths;
- pending output schema;
- expected resume command;
- failure information.

This information is diagnostic only and is not required in `agent2script`.

## Current non-goals

The current local Runtime deliberately does not add:

- an LLM client or Agent launcher;
- a custom Agent `spawn/join` concurrency runtime;
- a hidden generic retry engine;
- a distributed scheduler;
- a pluggable state-store abstraction without a concrete use case;
- speculative Step primitives without replay-tested semantics.

Retries remain explicit Python control flow or host correction after a validation error. Agent concurrency remains host-native.
