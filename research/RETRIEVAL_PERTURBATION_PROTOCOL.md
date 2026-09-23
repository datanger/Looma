# RQ2 retrieval-perturbation protocol (public-data re-basing)

## Why this protocol exists

The first RQ2 controlled comparison was executed on
`experiments/workloads/bounded_autonomy/scenarios.json`, a **self-authored** seven-scenario
suite. Its numbers (`experiments/results/rq2-controlled.json`) are therefore **not
admissible as paper evidence**: every task instance in them was written by us, so a
reviewer can fairly object that the tasks were shaped around Looma.

This protocol re-bases the same RQ2 question — *can an application absorb an environmental
perturbation without editing its control flow?* — onto **public benchmark task instances**
without authoring any task content.

The rule this file encodes:

> Task instances and gold labels come from a public benchmark.
> What we author is the **harness**: the deterministic perturbation transform, the tool
> surface, the acceptance gate, and the scoring. Those are the contribution, not a dataset.

## Public data source

Pinned, download-and-hash-verified, identical to the W2 A-RAG pipeline:

```text
repo_id   Ayanami0730/rag_test
revision  b9198a5a8702cc35c6df7542529357a9af95d928
files     <dataset>/questions.json
          <dataset>/chunks.json
datasets  musique, hotpotqa, 2wikimultihop
```

Produced by:

```bash
python -m experiments.case_studies.arag_host_native.prepare_public_data \
  --revision b9198a5a8702cc35c6df7542529357a9af95d928 \
  --subset-size 100 --seed aep-paper-v1 --output-root research-data/arag
```

The dev100 subsets are frozen by SHA-256 ranking of question ids
(`freeze_subset.py`), so the same 100 questions are selected on every machine
independently of source ordering.

**No question, answer, or paragraph in this experiment is written by us.** Every task
instance is a public benchmark item; every perturbation is a deterministic, invertible
transform applied to the public corpus and the public tool surface.

## What is perturbed, and what is not

Fixed across all conditions:

- the public question and its public gold answer;
- the public corpus content (chunks are never rewritten, only removed, renamed, or
  supplemented with other public chunks);
- the deterministic driver (the model stand-in);
- the action budget;
- the acceptance gate and the scoring.

Varied:

- which tools the environment exposes;
- whether chunk identifiers are stable;
- how much of the corpus survives truncation;
- which action set the application's orchestration declared.

## Perturbations

Six conditions. All are pure functions of `(public corpus, public question, seed)` and are
recorded in the run manifest by a content hash of the transformed corpus.

| id | transform | PAPER_PLAN perturbation it instantiates | dev/eval |
|---|---|---|---|
| `baseline` | none | reference condition | dev |
| `primary_tool_unavailable` | `semantic_search` is removed from the environment's tool surface | primary tool unavailable | dev |
| `source_id_renamed` | every chunk id is remapped to a deterministic opaque id; search returns snippets without the original ids | expected source missing | eval |
| `snippet_only` | search returns `(handle, snippet)` pairs; the handle→chunk mapping is only obtainable from `list_chunks` | additional verification is needed | eval |
| `evidence_withheld` | the corpus is truncated to a deterministic subset, which provably removes the gold evidence of some questions | insufficient evidence (negative control) | eval |
| `distractor_chunk` | one further public chunk, drawn deterministically from the same corpus, is attached as a competing source | one source conflicts with another | eval |

Only two transforms are visible on the development split. The four evaluation-split
transforms are what a real deployment discovers afterwards, and they are the reason the
route set frozen on the development split is expected to be insufficient.

`evidence_withheld` is a **negative control**, not an adaptation task. For the questions
whose gold evidence the truncation removed, the correct behaviour is to refuse. It is
scored separately and is excluded from the adaptation denominator.

## Action vocabulary and route ownership

Four actions:

```text
semantic_search   vector search over the corpus
keyword_search    lexical search over the corpus
read_chunk        resolve one chunk id to its text
list_chunks       enumerate the corpus catalog (handle -> chunk id)
```

Environment availability and application route are deliberately two different things:

- **environment unavailable** — the tool is not offered at all; the application receives
  an `unavailable` *observation* and is free to react. This is semantics.
- **route missing** — the application's orchestration declared no path to an action the
  deterministic driver wants. The session raises `RouteMissing`; the run is recorded as a
  dead end. This is structure, and it is the measured quantity.

Declared routes:

| paradigm | dev route set | eval route set | application code change |
|---|---|---|---|
| direct SDK / hand-written loop | `semantic_search, keyword_search, read_chunk` | `+ list_chunks` | requires an edit |
| AEP / Looma | none — the Host owns the route | none | zero |

The frozen development route already covers the obvious fallback (keyword search),
which is why `primary_tool_unavailable` is a development-split condition. What the
evaluation split adds is the one thing no amount of development testing on stable
identifiers would have revealed: a route that can turn an opaque handle into a
chunk id once the corpus has been re-keyed.

Looma's application file is byte-identical in both batches; the sha-256 of the application
file is recorded per batch to prove it.

## Deterministic driver (controlled mode)

RQ2's controlled mode requires *same model, same tools, same budget*
(`PAPER_PLAN.md`). Offline and in CI there is no model, so both paradigms are driven by the
same deterministic `AdaptiveRetrievalDriver`:

- it derives search terms from the question text (stop-word stripped, frequency ranked);
- it never reads the gold answer, the gold evidence ids, or any scoring field;
- it prefers `semantic_search` and falls back when the environment reports it unavailable;
- when search results carry opaque handles it calls `list_chunks` to resolve them;
- it reads the top-k discovered chunks;
- it declares insufficiency when no read chunk clears its lexical-support threshold.

Because the driver cannot perform multi-hop reasoning, **controlled mode does not measure
answer quality.** It measures whether the application can still reach the evidence under
perturbation. Answer-level accuracy (EM / F1 / contain-match) requires model-backed
Host-native runs and is reported separately.

## Metrics

Per instance:

| metric | definition |
|---|---|
| `evidence_recall` | gold-evidence chunks actually read / gold-evidence chunks present after the transform |
| `adaptive_success` | exact-evidence mode: `evidence_recall == 1`; proxy mode: `evidence_recall > 0` |
| `route_gap_count` | number of actions the driver wanted that the application declared no route for |
| `actions_used` | tool calls made |
| `outcome` | `answered_correct`, `answered_wrong`, `refused`, `dead_end`, `budget_exceeded` |

Aggregated: adaptive success rate per split; route gaps forced by the evaluation split;
mean actions and tool-path diversity; application SLOC and route-declaration delta SLOC;
application file sha-256 per batch.

Scoring fields never enter the `agent()` boundary. The gate attached to the boundary sees
only publicly derivable facts about the persisted retrieval session — non-empty result,
cited chunks that were actually read, no unread citations. This is enforced by
`tests/test_retrieval_perturbation.py::test_gate_feedback_never_leaks_gold`.

## Evidence presence proxy

The A-RAG `chunks.json` corpus ships no supporting-fact annotation for every dataset, so
the protocol reports two evidence notions:

1. **exact** — when the public question record carries gold evidence ids, recall is
   computed against them;
2. **proxy** — otherwise a chunk counts as gold evidence iff the normalized public gold
   answer occurs in its normalized text.

`answerable` is `evidence_present after the transform`, computed under the same rule. The
proxy is a lexical containment test, not a reasoning oracle; it is reported as a proxy in
every table and is never silently upgraded to ground truth.

## Fixture policy

`fixtures/tiny_corpus.json` is a hand-written corpus in the public files' **shape**. It
exists only so control-flow tests can run without network access. It carries
`"mode": "fixture"` and:

- it must never appear in a results table;
- the runner refuses to emit a `benchmark` payload for it and labels the run
  `mode: "fixture"`;
- CI runs the fixture for the tests and the pinned public data for the reported numbers.

## Threats to validity

1. **Deterministic driver, not a model.** Controlled mode isolates route flexibility; it
   cannot show answer quality and must never be presented as if it did.
2. **Proxy evidence.** The lexical containment proxy over-counts evidence for questions
   whose answer string occurs in unrelated paragraphs. Exact-id recall is reported
   whenever the public record allows it.
3. **Truncation is not adversarial.** The deterministic subset is content-independent; it
   is a reproducible way to create unanswerable instances, not a difficulty curve.
4. **`RouteMissing` conflates "unreachable" with "unattempted".** An application could in
   principle reach an equivalent action by another name. The action vocabulary is fixed to
   four tools for every paradigm, which limits but does not eliminate this.
5. **Refusal is not distinguishable from exhaustion.** A run recorded as `refused` may
   have refused for the right reason or simply run out of useful actions. The negative
   control is therefore reported separately and carries no weight in the adaptation claim.
6. **One dataset family.** All six conditions run on retrieval corpora. Nothing here
   generalises to stateful business tools; that needs the tools benchmark (W3).

## Reproduction

```bash
python -m experiments.workloads.retrieval_perturbation.run_perturbation \
  --data-root research-data/arag \
  --datasets musique,hotpotqa,2wikimultihop \
  --paradigms direct_sdk,looma \
  --limit 100 \
  --expect-public \
  --output experiments/results/rq2-retrieval-perturbation.json
```

Exit codes: `0` normal, `2` harness error, `3` a paradigm's optional dependency is missing.

`--expect-public` refuses any dataset directory that is not one of the three pinned
benchmark names, so a fixture run cannot be mistaken for a result. CI executes the command
above in `.github/workflows/research-retrieval-perturbation.yml`.