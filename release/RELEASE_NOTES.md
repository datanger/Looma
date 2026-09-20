# Looma v0.1.3

Host-native AEP guidance and integrated stock-analysis Agent release.

## New in v0.1.3

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
- Kept concurrency host-native: Looma describes parallelizable analysis work but never launches Agents or subagents.
- Updated the packaged AEP Skill with recoverable external-data fallback and provenance rules.
- Consolidated repository instructions into the Codex-standard `AGENTS.md`; removed the nonstandard duplicate `AGENT.md`.
- Simplified the example set to one integrated, realistic case and aligned README/design/AEP docs with the implementation.
- CI continues to cover Python 3.10, 3.11, 3.12, and 3.13, plus wheel install and packaged-Skill smoke checks.

## Compatibility

- Public Runtime API remains `@workflow`, `step()`, and `agent()`.
- `script2agent.prompt` is unchanged.
- `agent2script` remains exactly `script + args`.
- Looma still never launches Codex, Claude Code, SDW, another Agent process, or subagents.

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.3/looma_runtime-0.1.3-py3-none-any.whl
```

Looma remains experimental.
