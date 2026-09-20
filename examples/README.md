# Looma example

Looma intentionally keeps **one integrated example**:

- [stock_analysis_agent/](stock_analysis_agent/) — a short-term stock analysis Agent that combines AKShare market-data scripts, recent-news web research, deterministic evidence checks, a research loop, structured Agent results, and optional host-native subagent concurrency.

The default target is **宇树科技 (688836)**, but the workflow accepts another A-share name/code.

The example is deliberately split into small workflow stages so that code owns deterministic data processing while the current host Agent owns web research and semantic analysis.
