# Controlled RQ2 comparison — bounded autonomy under perturbation

Four programming models, one perturbation suite, one driver, one budget. The only thing
that varies is **who owns the action route**.

```text
scenario (public facts only)  →  application orchestration  →  Result Contract
                                          │
                                          ├─ who decides which tool actions exist?
                                          └─ what does the held-out split cost?
```

## Reproduce

```bash
export PYTHONPATH=$PWD:$PWD/src
python -m pip install -e . pytest -r experiments/requirements-phase1.txt
python -m experiments.workloads.bounded_autonomy.controlled.run_controlled \
  --output experiments/results/rq2-controlled.json
python -m pytest tests/test_bounded_autonomy.py tests/test_bounded_autonomy_controlled.py
```

Exit codes: `0` ok · `2` harness error · `3` an optional framework is missing (re-run with
`--allow-missing-dependencies` to record those paradigms as `dependency_missing` instead
of failing). `experiments/results/` is gitignored; CI writes to `research-results/`.

Scope flags: `--paradigms direct_sdk,looma --routes dev,widened`.

## Layout

| path | role | counted as application code? |
| --- | --- | --- |
| `protocol.py` | shared tool surface (`ToolSession`), report building, `RouteMissing` | no — shared harness |
| `policy.py` | `AdaptiveDriverPolicy`: the deterministic model stand-in | no — shared harness |
| `run_controlled.py` | runs the matrix, scores with `validator.score_result`, aggregates | no — shared harness |
| `<paradigm>/workflow.py` | the application under comparison | yes |
| `<paradigm>/widened.py` | the route/topology edit the held-out split forces | yes, only in the `widened` batch |
| `looma/host_driver.py` | simulates the external Host (Looma's `agent()` side) | **no** — `excluded_harness_files` |

`looma/host_driver.py` is the AEP Host: it runs the driver policy against a host-owned
session, writes the result file, and resumes the suspended workflow through
`looma handoff`, which enforces the Result Contract and the Resume Contract before the
original command is allowed to run again. Its SLOC is reported separately as
`host_driver_sloc` and never mixed into `application_sloc`.

## Route semantics

`ToolSession(scenario_id, allowed_actions, max_actions=12, stage="plan")` is the whole tool
surface. `execute()` raises `RouteMissing` when the requested action is not in
`allowed_actions`. That is deliberate:

* a missing route is an **observation** the caller may act on (`record_unsupported()`),
  not a crash — otherwise "the framework crashed" would be a straw-man failure mode
  rather than a statement about route ownership;
* `route_gaps` in the results are therefore diagnostic data: which action the held-out
  split needed and did not have.

`list` is the discovery action. A paradigm that declares only `read` has no way to learn
about a renamed or replaced source; that is exactly the `dev → eval` gap the comparison
measures.

## The widening ablation

| batch | what it means |
| --- | --- |
| `--routes dev` | the route set an author freezes after the development split |
| `--routes widened` | the route set the held-out split turns out to require |

`route_declaration_delta_sloc` = `sloc(widened) − sloc(dev)` is the cost of that second
edit. For `looma` it is `0` by construction: `declared_routes` is empty, the application
file and its SHA-256 are identical in both batches, and the Host supplies `read` + `list`
in both.

For `langgraph`, widening is not a permission-list edit but a topology edit: the dev graph
has no node able to issue `list`, so `widened.py` adds a `discover` node and the
conditional edge that reaches it.

## Metrics

* `atsr_dev`, `atsr_eval` — adaptive task success rate per split, scored by
  `validator.score_result` (the experiment-side scorer, which knows the oracle).
* `eval_route_gaps` — how many held-out rows hit a `RouteMissing`.
* `tool_path_diversity` — distinct tool paths taken across scored rows.
* `mean_actions`, `sloc`, `route_declaration_delta_sloc`, `application_sloc`,
  `host_driver_sloc`.
* `environment` — python, platform, commit, `worktree_dirty`, framework versions.

Scoring is separate from the acceptance gate on purpose: the gate's `problems` are fed back
to the Agent on retry and may only contain publicly derivable facts. See
`../validator.py` and `research/BOUNDED_AUTONOMY_PROTOCOL.md`.

## Caveats

These numbers come from a deterministic driver policy, not a model, and they measure route
flexibility and orchestration overhead — **not** Agent output quality. `langgraph` and
`microsoft_agent_framework` require `langgraph==1.2.11` / `agent-framework-core==1.19.0`;
where those are absent their rows are reported with `dependency_missing: true` and the
table is produced by CI.