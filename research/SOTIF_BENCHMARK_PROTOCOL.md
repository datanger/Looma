# W3 / SOTIF-regulatory benchmark protocol

## Purpose

The regulatory workload tests whether AEP can combine:

- Host-native multi-hop evidence acquisition;
- local autonomy inside an Agent boundary;
- deterministic input/result contracts;
- program-owned evidence/acceptance gates;
- explicit abstention when the corpus is insufficient.

The paper must not reproduce copyrighted standards text without permission.

## Dataset design

Target 300–500 expert-reviewed questions if feasible. A smaller 150–200 item
pilot is acceptable before full annotation.

Recommended strata:

- single-clause lookup;
- intra-document multi-hop;
- cross-document multi-hop;
- definition → requirement;
- requirement → exception;
- version/applicability;
- conflicting evidence;
- unanswerable / missing-evidence.

Every item should record a gold evidence chain. Multi-hop items should preserve
the evidence order when order is semantically important.

## Source policy

For redistributable public regulations, passages may be packaged when the source
license permits it.

For ISO/proprietary standards:

- do not commit the standard text to this repository;
- store document/version/clause/page or another stable locator;
- keep the actual corpus in an authorized private location;
- publish benchmark metadata/questions only to the extent permitted;
- report exact corpus version and access procedure in the paper artifact.

The included synthetic fixture is solely a tooling test and must never be mixed
into real SOTIF accuracy numbers.

## Annotation

Each real item should be independently reviewed by at least two domain-aware
annotators where possible. Resolve disagreements before freezing the test split.

Record:

- answerable label;
- accepted answer or answer criteria;
- supporting evidence ids;
- minimum hop count;
- task category;
- document versions;
- disagreement/adjudication metadata.

## Metrics

Primary:

- answer correctness;
- answerability / abstention F1;
- evidence Recall / Precision;
- evidence-chain completion;
- unsupported-claim rate.

Secondary:

- Host/tool calls;
- evidence tokens;
- latency;
- contract retries;
- human intervention.

Report results by task stratum, especially multi-hop and unanswerable subsets.

## Comparison

Use the same frozen corpus, question split, retrieval tools, and evaluator for:

- conventional internal-Agent baseline;
- graph/workflow baseline;
- Host-native AEP.

Where an identical underlying model is possible, run a controlled comparison.
Then separately run frontier Host Agents to evaluate capability inheritance.

## Stability

Malformed Host outputs must be rejected by the output schema. Structurally
malformed task context must be rejected by the Agent input contract before
suspension. Evidence ids not present in the item's catalog are rejected by the
deterministic acceptance gate.
