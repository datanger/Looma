# Looma v0.1.1

Patch release adding strict resume-command validation.

Looma is a Python implementation of **Agent-Embedded Programming (AEP / 智能体嵌入式编程)**.

## New in v0.1.1

- Strict validation of Agent-returned `agent2script` against `script2agent.expected_output`.
- Exact-match enforcement for `script`, `args`, and top-level fields.
- New guarded handoff executor:
  `looma handoff --request <script2agent.json> --response <agent2script.json>`.
- Mismatched commands are never executed.
- Validation failures return exit code `76` and a structured `AGENT2SCRIPT_ERROR` payload containing expected vs actual output.
- Handoff verifies that the Agent result JSON exists before resume.
- Validated resumes restore the original workflow `cwd` from persisted state.
- Tests verify that a mismatched command cannot produce side effects and that an exact match is executed.
- Bundled Agent-Embedded Programming Skill documents the validation/retry contract.

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.1/looma_runtime-0.1.1-py3-none-any.whl
```

Looma remains experimental; persistence and host-adapter APIs may evolve.
