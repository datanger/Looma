# A-RAG controlled case-study protocol

## Goal

Evaluate AEP's central claim on a real agentic-retrieval workload:

> An AEP application can reuse the already-running Host Agent as the retrieval
> controller instead of rebuilding an internal Agent controller and LLM client.

The original A-RAG implementation remains the baseline. The AEP version reuses
the same A-RAG corpus, keyword search, semantic search, chunk read, embedding
index, and evaluation script.

## Compared systems

### Original A-RAG

```text
question
  → BaseAgent
    → LLMClient
      → ToolRegistry
        → keyword_search / semantic_search / read_chunk
```

### Host-native AEP / Looma

```text
question
  → Looma agent() boundary
    → already-running Host Agent
      → bridge.py
        → same A-RAG ToolRegistry
          → keyword_search / semantic_search / read_chunk
```

The bridge is deterministic and contains no model client.

## Controlled variables

For the model-controlled comparison, freeze:

- dataset split and question order;
- A-RAG repository commit;
- chunks and embedding index;
- embedding model;
- available retrieval tools;
- maximum semantic rounds;
- answer-evaluation procedure.

Where a comparable underlying model can be exposed through both architectures,
also freeze model/version, temperature/reasoning setting, and token budget.

The real Host-native experiment is reported separately when the Host provides
additional capabilities that cannot be made identical to the API baseline.

## Primary datasets

Start with:

1. MuSiQue
2. HotpotQA
3. 2WikiMultiHopQA

A small development subset is used first. Full benchmark runs start only after
the execution and logging protocol is frozen.

## Outputs

`batch_workflow.py` writes A-RAG-compatible JSONL fields plus AEP-specific
trace fields:

- `pred_answer`
- `gold_answer`
- `total_retrieved_tokens`
- `retrieval_logs`
- `chunks_read_count`
- `chunks_read_ids`
- `host_rounds`
- `tool_path`
- `cited_chunk_ids`
- `confidence`
- boundary acceptance status

The original A-RAG `scripts/eval.py` can therefore be reused for answer-level
evaluation after the Host-native run.

## Metrics

### Quality

- A-RAG LLM-Evaluation Accuracy;
- Contain-Match Accuracy;
- answer rate;
- evidence/chunk citation validity.

### Retrieval / trajectory

- retrieved tokens;
- chunks read;
- retrieval calls by tool;
- Host semantic rounds;
- tool-path length;
- duplicate read attempts.

### Engineering

- controller/model-client code bypassed;
- AEP application orchestration SLOC;
- framework-specific constructs;
- code changes required to switch Host.

### Efficiency

For comparable model conditions:

- wall-clock latency;
- model calls;
- input/output tokens where observable;
- retrieval tokens.

Do not interpret the deterministic CI smoke driver as a quality or latency
benchmark.

## Execution sequence

1. Download the public A-RAG benchmark data.
2. Build the same Qwen3-Embedding-0.6B index used by the baseline.
3. Run Original A-RAG on a frozen development subset.
4. Run `batch_workflow.py` on the identical subset under one Host Agent.
5. Reuse A-RAG's evaluator on both prediction files.
6. Repeat with at least two additional Host/model configurations without
   modifying `batch_workflow.py`.
7. Expand to the full selected benchmark splits after the protocol is stable.

## Host-native command

Example:

```bash
python -m experiments.case_studies.arag_host_native.batch_workflow \
  --questions /path/to/data/musique/questions.json \
  --config /path/to/arag/configs/test_musique.yaml \
  --output results/aep-musique/predictions.jsonl \
  --sessions-dir results/aep-musique/sessions \
  --limit 100
```

Run this command from the Coding Agent host being evaluated. Looma will suspend
at each `agent()` boundary; that same Host must perform the retrieval task and
resume the workflow.

## Interpretation

This case study tests two distinct hypotheses and they must not be conflated:

1. **Controlled architecture hypothesis:** removing the nested internal Agent
   does not reduce quality when model/tool conditions are controlled.
2. **Capability-inheritance hypothesis:** an unchanged AEP program can improve
   when executed by a more capable Host Agent.

The second is a practical systems property, not proof that the programming
abstraction alone causes higher model intelligence.

## Reproducibility utilities now implemented

Freeze a development subset independently of source ordering:

```bash
python -m experiments.case_studies.arag_host_native.freeze_subset \
  --questions data/musique/questions.json \
  --size 100 \
  --seed aep-paper-v1 \
  --output research-data/musique-dev100.json \
  --manifest research-data/musique-dev100.manifest.json
```

Record immutable file digests for each baseline/AEP run with
`run_manifest.py`.

After both prediction files have been evaluated, produce a paired comparison:

```bash
python -m experiments.case_studies.arag_host_native.compare_predictions \
  --baseline results/original/predictions.jsonl \
  --aep results/aep/predictions.jsonl \
  --bootstrap 10000 \
  --output results/paired-comparison.json
```

The comparison joins by question id, reports deterministic Contain-Match
accuracy, answer rate, retrieval-token/tool-call deltas, 95% paired bootstrap
intervals, and an exact McNemar test for paired Contain-Match correctness.
If both inputs already contain A-RAG `llm_accuracy` fields, it also reports the
paired LLM-accuracy delta.

These utilities intentionally do not invent missing LLM-judge scores.
