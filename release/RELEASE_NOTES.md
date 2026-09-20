# Looma v0.1.4

Clean patch release for the host-native AEP guidance and integrated stock-analysis Agent work.

> v0.1.4 supersedes v0.1.3. The v0.1.3 wheel had package metadata version 0.1.3 but an outdated `looma.__version__` constant. CI detected the mismatch after publication; v0.1.4 corrects it and strengthens the release gate so the same class of issue cannot be published again.

## New since v0.1.2

- Added a single integrated `stock_analysis_agent` example that exercises real AEP control flow across multiple scripts and multiple Agent boundaries.
- Added AKShare-first market-data acquisition with a recoverable host-native fallback:
  - provider/package/network failures become explicit Workflow branches;
  - the current Host Agent may use native web/search/browser tools to obtain sourced real market data;
  - live fallbacks are forbidden from fabricating, interpolating, or estimating business facts;
  - fixtures remain CI-only and are never treated as live evidence.
- Added deterministic evidence and analysis gates:
  - recent-news evidence is revalidated after research loops;
  - analysis results are checked for required tracks, evidence references, and confidence range;
  - final output is explicitly marked `complete` or `insufficient_evidence`.
- Refined the AEP responsibility model:
  - Program owns control flow and acceptance criteria.
  - Agent owns semantic reasoning and evidence acquisition.
  - Runtime owns continuity.
- Kept concurrency host-native: Looma describes parallelizable work but never launches Agents or subagents.
- Updated the packaged AEP Skill with recoverable external-data fallback and provenance rules.
- Consolidated repository instructions into the Codex-standard `AGENTS.md`; removed the duplicate `AGENT.md`.
- Simplified examples to one integrated, realistic case and aligned README/design/AEP docs with the implementation.

## Release integrity

- `pyproject.toml`, `release/VERSION`, and `looma.__version__` are all `0.1.4`.
- The release workflow installs the built wheel before publishing it.
- The release gate verifies installed package metadata, `looma.__version__`, CLI availability, and the packaged AEP Skill.
- CI covers Python 3.10, 3.11, 3.12, and 3.13.

## Compatibility

- Public Runtime API remains `@workflow`, `step()`, and `agent()`.
- `script2agent.prompt` is unchanged.
- `agent2script` remains exactly `script + args`.
- Looma still never launches Codex, Claude Code, SDW, another Agent process, or subagents.

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.4/looma_runtime-0.1.4-py3-none-any.whl
```

Looma remains experimental.
