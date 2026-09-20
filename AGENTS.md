# Looma repository instructions

- Preserve the public programming model: `@workflow`, `step()`, `agent()`.
- Looma runs inside an already-existing Coding Agent host. Never launch Codex, Claude Code, SDW, another Agent process, or a subagent from Looma through a CLI, SDK, API, or subprocess.
- Host-native reasoning, tools, subagents, concurrency, workspace isolation, and result aggregation belong to the host. Looma only describes work and manages the program boundary.
- Do not add direct LLM API dependencies. Model access belongs to the coding-agent host.
- Preserve the exact fixed `script2agent.prompt` text defined in `looma.protocol` and the bundled Skill.
- Keep `agent2script` limited to exactly `script` and `args`.
- Treat `expected_output` as a strict Resume Contract. A returned command must be validated before execution.
- Validate `output.result_file` against `output.output_schema` before resume, and keep runtime-side validation as a defense if handoff is bypassed.
- Same-command resume is a core invariant: the default `expected_output` must re-run the original Python invocation, not expose an internal resume helper.
- Prefer deterministic replay and persisted events over Python source rewriting or restoring raw Python call stacks.
- Any replay-visible feature must include process restart/resume tests.
- Side-effectful work must be representable through `step()` or another durable primitive.
- Durable state writes should remain atomic and recoverable from interrupted writes.
- Independent copies of the same command may be isolated with `LOOMA_RUN_KEY`; the same run key must continue to refer to one logical active run.
- The package must remain installable as a pure Python wheel on Python 3.10+.
- Keep `src/looma/skills/agent-embedded-programming/SKILL.md` aligned with public API and host-contract changes.
