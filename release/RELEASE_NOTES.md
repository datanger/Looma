# Looma v0.1.2

Reliability and runtime-completeness release for **Agent-Embedded Programming (AEP / 智能体嵌入式编程)**.

## New in v0.1.2

- Structural Agent result validation before resume.
  - Dataclass output schemas are emitted as structural JSON Schema.
  - Handoff rejects missing, invalid, or schema-incompatible `output.result_file`.
  - Runtime replay validates structured results again as a second line of defense.
- New `looma inspect [run-id]` command for event history, pending Agent Contract, expected resume command, and failure state.
- Independent same-command workflow instances through `LOOMA_RUN_KEY`.
- Failed/completed workflows release their active invocation pointer; user `SystemExit` now finalizes durable state correctly.
- Durable JSON state writes use atomic same-directory replacement.
- Resume command validation from v0.1.1 remains strict: `agent2script` must exactly equal `expected_output`.
- Host-native execution semantics are now explicit:
  - Looma never launches Codex, Claude Code, SDW, or subagents.
  - Agent/subagent concurrency belongs entirely to the already-running host.
- README, design documentation, bundled AEP Skill, repository instructions, and examples were aligned with the host-native model.
- Removed speculative Roadmap items that either duplicate implemented functionality or do not belong in Looma's current runtime scope.
- Expanded regression tests cover result-schema guards, direct-resume defense, workflow inspection, run isolation, failure cleanup, loops, multi-script flows, and multi-stage Agent/Script workflows.
- Python 3.10, 3.11, 3.12, and 3.13 are tested in CI; the built wheel is reinstalled and CLI/Skill packaging is smoke-tested.

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.2/looma_runtime-0.1.2-py3-none-any.whl
```

Looma remains experimental. The current scope is a local durable Python runtime for host-native AEP workflows; distributed scheduling and Agent-launcher responsibilities are intentionally out of scope.
