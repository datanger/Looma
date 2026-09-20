# A-RAG → Host-native AEP case study

This case study uses the current `datanger/arag` code **without modifying its
internal Agent implementation**. The bridge imports only A-RAG's retrieval
components and deliberately does not instantiate `BaseAgent` or `LLMClient`.

```text
Original A-RAG

application
  → BaseAgent
    → LLMClient
      → ToolRegistry
        → keyword_search / semantic_search / read_chunk


AEP case

already-running Host Agent
  ↕ Looma agent boundary
ordinary Python workflow
  → bridge.py
    → unmodified A-RAG ToolRegistry
      → keyword_search / semantic_search / read_chunk
```

The Host determines the retrieval trajectory. Looma constrains the final
boundary through an output schema and a deterministic acceptance gate. The gate
also checks that every cited chunk was actually read in the persisted A-RAG
retrieval session.

## Deterministic bridge

```bash
python -m experiments.case_studies.arag_host_native.bridge \
  --config /path/to/arag-config.yaml \
  --session .looma/arag-session.json \
  --no-semantic \
  list
```

Tool call example:

```bash
python -m experiments.case_studies.arag_host_native.bridge \
  --config /path/to/arag-config.yaml \
  --session .looma/arag-session.json \
  --no-semantic \
  call --tool keyword_search \
  --arguments '{"keywords":["Einstein"],"top_k":5}'
```

The CI smoke test uses keyword search and chunk read only. The paper-quality
multi-hop experiment will additionally use A-RAG's existing semantic index and
the public MuSiQue / HotpotQA / 2Wiki evaluation pipeline.

## Important interpretation

The deterministic `smoke_driver.py` is only an integration test. It simulates a
Host response so CI can prove that A-RAG retrieval state, Looma suspension,
Result Contract validation, Resume Contract validation, and replay work
together. It does not measure Host-Agent intelligence or answer quality.

## Batch benchmark workflow

For the paper-quality multi-hop evaluation, use:

```bash
python -m experiments.case_studies.arag_host_native.batch_workflow \
  --questions /path/to/data/musique/questions.json \
  --config /path/to/arag/configs/test_musique.yaml \
  --output results/aep-musique/predictions.jsonl \
  --sessions-dir results/aep-musique/sessions \
  --limit 100
```

The output intentionally follows A-RAG's prediction field conventions so the
original `scripts/eval.py` can evaluate the Host-native result. See
`research/ARAG_CASE_PROTOCOL.md` for the controlled comparison protocol.
