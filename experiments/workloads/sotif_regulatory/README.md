# W3 — SOTIF / Regulatory Iterative Analysis

This workload is the domain-oriented AEP case study. It is designed to evaluate
multi-hop evidence use, version-aware regulatory reasoning, abstention, and
program-owned acceptance gates.

The repository contains only **synthetic CI fixtures**. They are explicitly
invented and must not be presented as ISO 21448 content.

Real benchmark data should be supplied separately as an authorized corpus.

## Benchmark item

Each item records:

- question and optional scenario;
- task type;
- answerable/unanswerable label;
- evidence catalog;
- document/version/locator metadata;
- gold evidence chain;
- optional gold answer;
- minimum evidence-hop requirement.

The evidence catalog allows a record to omit `text` when redistribution is not
permitted. In that case the Host must access the authorized external/local
source identified by the experiment environment.

## Validate tooling

```bash
python - <<'PY'
from experiments.workloads.sotif_regulatory.dataset import load_benchmark
print(load_benchmark(
    "experiments/workloads/sotif_regulatory/fixtures/synthetic_examples.json"
)["schema"])
PY
```

## AEP workflow

```bash
python -m experiments.workloads.sotif_regulatory.workflow \
  --dataset /path/to/authorized-benchmark.json \
  --item QUESTION_ID \
  --output results/QUESTION_ID.json
```

The Host chooses the evidence-reading path. The program constrains input/output
schemas and applies a deterministic final validation gate.

## Evaluation

```bash
python -m experiments.workloads.sotif_regulatory.evaluate \
  --dataset benchmark.json \
  --predictions predictions.json \
  --output evaluation.json
```

Current deterministic metrics include answerability accuracy, answer match,
evidence precision/recall, minimum-hop satisfaction, and strict task success.
A semantic/human correctness judgment can be added later, but must not replace
the evidence-chain metrics.
