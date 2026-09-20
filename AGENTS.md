# Looma repository instructions

- Preserve the public programming model: `@workflow`, `step()`, `agent()`.
- Do not add direct LLM API dependencies. Model access belongs to the coding-agent host.
- Preserve the exact fixed `script2agent.prompt` text defined in `looma.protocol` and the bundled Skill.
- Keep `agent2script` limited to `script` and `args`.
- Same-command resume is a core invariant: the default `expected_output` must re-run the original Python invocation, not expose an internal resume helper.
- Prefer deterministic replay and persisted events over Python source rewriting or restoring raw Python call stacks.
- Any replay-visible feature must include process restart/resume tests.
- Side-effectful work must be representable through `step()` or another durable primitive.
- The package must remain installable as a pure Python wheel on Python 3.10+.
- Keep the bundled `llm-driven-programmatic-coding` Skill aligned with public API changes.
