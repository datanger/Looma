# RQ6 — Host portability / capability inheritance protocol

## Hypothesis

An AEP application can run under different Host Coding Agents without changing
the application Workflow source. Host improvements may therefore change task
quality without requiring application-level Agent-workflow redesign.

This experiment tests a systems property, not a claim that one commercial Host
is universally better than another.

## Invariant

For all compared Host runs:

```text
workflow_sha256 must be identical
```

The following must also remain fixed within one comparison block:

- dataset and split;
- input order;
- deterministic Python tools;
- output schema;
- acceptance gates;
- retry limit;
- Looma version;
- A-RAG corpus/index for retrieval experiments.

Only Host/model/version may change.

## Run procedure

1. Check out the frozen Looma experiment commit.
2. Start the Host being evaluated.
3. Run the same AEP command from that Host.
4. Allow the Host to execute only capabilities permitted by the workload.
5. Save raw task results and evaluation metrics.
6. Record a manifest with:

```bash
python -m experiments.host_portability.record_run \
  --host codex \
  --host-version "<exact version>" \
  --model "<exact model/config>" \
  --workflow experiments/case_studies/arag_host_native/batch_workflow.py \
  --results results/aep-musique/predictions.jsonl \
  --metrics results/aep-musique/eval_summary.json \
  --output results/aep-musique/run-manifest.json
```

7. Repeat for the next Host **without modifying the workflow file**.
8. Verify identical source hashes:

```bash
python -m experiments.host_portability.compare_runs \
  results/host-a/run-manifest.json \
  results/host-b/run-manifest.json \
  results/host-c/run-manifest.json
```

The comparison tool rejects a portability comparison if Workflow hashes differ.

## Metrics

### Portability

- workflow modification LOC;
- identical-workflow rate;
- setup/config changes outside Workflow;
- Result Contract compliance;
- Resume Contract compliance;
- completion rate.

### Capability inheritance

- task-specific quality;
- evidence quality;
- tool-use success;
- adaptive success on perturbed cases;
- Host semantic rounds;
- retrieved tokens where applicable.

## Reporting

Report the exact Host and model versions and the experiment date. Host products
can change independently of the repository, so a portability result without a
version/date is not reproducible enough for the paper.

Do not interpret a stronger Host result as proof that AEP itself caused the
model to become more intelligent. The AEP claim is that the unchanged
application can *inherit* that Host capability.
