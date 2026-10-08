# AEP + GEPA-style optimization

This example keeps Looma's Agent-Embedded Programming model intact while adding a small GEPA-style loop:

1. Python owns the candidate, evaluation, acceptance rule, and frontier state.
2. `step()` evaluates the candidate durably.
3. `request_reflection()` hands traces and actionable side information to the current Host Agent through `agent()`.
4. The Host Agent writes a structured `CandidateProposal` result and returns the exact `agent2script` command.
5. `step(accept_proposal, ...)` applies deterministic gates and records the accepted candidate.

The evaluator is deterministic and local. The example does not import the external `gepa` package, call a model API, launch another Agent, or require network access.

Run it from the repository root:

```bash
PYTHONPATH=src python examples/gepa_optimization/workflow.py
```

The first run exits with code `75` and emits a `script2agent` request. The current Host Agent should write a JSON `CandidateProposal` to the request's `output.result_file`, save the exact `expected_output` object as an `agent2script` response, then run:

```bash
PYTHONPATH=src python -m looma.cli handoff \
  --request .looma/runs/<run-id>/events/0001-script2agent.json \
  --response /path/to/agent2script.json
```

`handoff` validates the result and resumes the original Python command. The evaluation `step()` is replayed from its persisted result rather than executed again.
