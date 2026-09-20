# Initial experimental results

These are engineering checkpoints, not final paper claims. Final tables require repeated runs, frozen hardware/environment metadata, statistical analysis, and the model-backed experiments.

## Phase 0 — contract reliability

The current fault-injection harness covers a valid control plus malformed/missing Agent results, schema violations, invalid resume output, and replay divergence. The first successful CI run observed:

- 8/8 scenarios behaved as expected;
- 7/7 invalid boundary cases were rejected;
- 0 false acceptances;
- the valid control completed.

This does not establish exactly-once side effects for a crash that occurs inside a side-effecting `step()` before durable persistence.

## Phase 0 — runtime scaling checkpoint

One GitHub-hosted Python 3.12 run produced the following checkpoint:

| Durable steps before Agent boundary | Initial run | Guarded resume | state.json |
|---:|---:|---:|---:|
| 10 | 71.8 ms | 104.6 ms | ~4.9 KB |
| 100 | 312.0 ms | 110.5 ms | ~41.2 KB |
| 1000 | 8533.3 ms | 166.8 ms | ~404.8 KB |

The 1000-step first-pass cost suggests that repeated full-state persistence is a likely scalability bottleneck worth optimizing. One run is insufficient to infer an asymptotic complexity.

## Phase 1 — W1 controlled semantic fixture

CI run: `35511387807`, commit `03a27efa04400788a605b88ccec35cc2de1f8ca3`.

All four implementations completed the same five scenarios with identical fixture semantics:

| Method | Task success | Orchestration SLOC | Functions | Classes | Calls | Median process time* |
|---|---:|---:|---:|---:|---:|---:|
| Direct SDK | 5/5 | 57 | 2 | 0 | 22 | 39.8 ms |
| LangGraph | 5/5 | 101 | 10 | 1 | 39 | 790.4 ms |
| Microsoft Agent Framework | 5/5 | 70 | 3 | 0 | 28 | 243.8 ms |
| Looma | 5/5 | 57 | 2 | 0 | 18 | 515.7 ms |

\*The timing is a single fixture-mode CI run and includes Python/framework startup. Looma additionally performs process suspension, guarded handoff, same-command replay, and multiple process launches. These numbers therefore measure fixture orchestration overhead, not real Agent end-to-end latency, and must not be used as a final performance ranking.

Looma's benchmark-only `host_driver.py` is excluded from application SLOC because a real AEP application relies on the already-running Host Agent; the driver only deterministically simulates that Host in CI.

## What these checkpoints support

They currently support only narrow statements:

- the four W1 implementations are behaviorally equivalent under the deterministic semantic fixture;
- the Looma application expresses the W1 control flow with substantially fewer framework-specific constructs than the LangGraph implementation in this benchmark;
- Looma pays measurable suspend/replay/process overhead that must be reported rather than hidden;
- Looma's current boundary guards reject the tested invalid outputs.

They do **not** yet support claims that Looma has higher Agent output quality, lower real-world end-to-end latency, or shorter human development time.
