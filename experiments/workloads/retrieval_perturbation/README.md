# RQ2 retrieval-perturbation workload

Re-bases the RQ2 bounded-autonomy comparison onto **public multi-hop QA
instances** so that no task instance is authored by us. The literary source of
truth is `research/RETRIEVAL_PERTURBATION_PROTOCOL.md`.

```text
public corpus + public question          ← pinned A-RAG revision, hashed
        ↓
deterministic perturbation transform     ← ours (the contribution)
        ↓
same tool surface, same driver, same budget for every paradigm
        ↓
program-owned acceptance gate            ← sees no gold answer
        ↓
experiment-side scoring                  ← the only place gold is read
```

## Layout

| path | role |
|---|---|
| `corpus.py` | loads `questions.json` / `chunks.json` as published; records the observed shape and file digests |
| `injectors.py` | the six deterministic perturbations and the route sets |
| `driver.py` | deterministic retrieval driver (the model stand-in for controlled mode) |
| `protocol.py` | `RetrievalSession` tool surface, `RouteMissing`, boundary gate, scoring |
| `instance.py` | instance construction; writes the **gold-free** payload paradigms read |
| `direct_sdk/` | hand-written loop that owns its route set |
| `looma/` | AEP application (`workflow.py`) + Host simulator (`host_driver.py`) |
| `fixtures/fixture/` | hand-written corpus in the public shape — control-flow tests only |

## Run

```bash
# real numbers: pinned public data, produced by the A-RAG data workflow
python -m experiments.workloads.retrieval_perturbation.run_perturbation \
  --data-root research-data/arag \
  --datasets musique,hotpotqa,2wikimultihop \
  --limit 100 \
  --expect-public \
  --output experiments/results/rq2-retrieval-perturbation.json

# control-flow only, never reportable
python -m experiments.workloads.retrieval_perturbation.run_perturbation \
  --data-root experiments/workloads/retrieval_perturbation/fixtures \
  --datasets fixture \
  --output /tmp/rq2-retrieval-fixture.json
```

Exit codes: `0` normal, `2` harness error, `3` optional dependency missing.
`--expect-public` refuses any dataset directory that is not one of the three
pinned benchmark names, so a fixture run cannot be mistaken for a result.

## What is measured

* `adaptive_success` — the application still reached the public gold evidence
  under the perturbation, split into development and held-out conditions;
* `eval_route_gaps` — how many actions the held-out split needed that the frozen
  application route could not reach;
* `route_declaration_delta_sloc` / `application_sha256` — what widening the route
  cost, and whether the AEP application changed at all;
* `false_answers` / `correct_refusal_rate` — the negative control, reported
  separately and carrying no weight in the adaptation claim.

## What is **not** measured

Answer quality. The deterministic driver cannot reason across hops, so
contain-match, EM and F1 from this runner mean nothing. Those need model-backed
Host-native runs. Any table built from this workload must say so.