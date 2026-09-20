# RQ2 — Bounded autonomy protocol

## Claim being tested

AEP keeps application-level control flow fixed while allowing the already-running
Host Agent to choose and revise its internal tool/reasoning path inside an
explicit semantic boundary.

The target property is:

> interface stability with path autonomy.

This is not a claim that arbitrary Agent behavior is safe. Tool permissions are
Host-controlled and final continuation remains guarded by Result/Resume/Acceptance
contracts.

## Perturbation workload

The implemented suite currently includes:

- normal path;
- preferred source unavailable;
- authoritative source renamed/migrated;
- stale conflicting evidence;
- expected review missing but equivalent audit evidence available;
- genuinely insufficient evidence after adaptation.

The Host receives only the public task/requirements and a deterministic source
environment. It may call `list` and `read` operations in any order.

## Sanity baseline

`sanity.py` includes:

1. a **static-route diagnostic** that follows a predefined source path;
2. an **adaptive oracle** that is allowed to discover available sources.

The oracle is not an Agent and its success is **not** a paper result about AEP
intelligence. Its purpose is only to verify that the benchmark actually contains
perturbations where fixed routes break but adaptive paths can succeed.

## Real evaluation

Run the exact same `workflow.py` under each Host Agent. Record:

- scenario success;
- contract rejection/retry count;
- Host rounds;
- source/tool path;
- human intervention count;
- Workflow source hash;
- task quality.

No Workflow code may be modified between the unperturbed and perturbed tasks.

### Adaptive Task Success Rate

```text
ATSR = successful perturbed scenarios / all perturbed scenarios
```

Report the unperturbed normal case separately so that adaptive performance is not
inflated by easy nominal execution.

## Comparison to conventional workflows

For a fair framework comparison, conventional implementations must be given the
same tool environment and task information. We should compare at least:

- predefined fixed route;
- framework-specific dynamic Agent/tool loop using the same model;
- AEP Host-native execution.

The fixed route is a diagnostic lower bound, not a stand-in for all LangGraph or
Agent Framework programs.

## Stability interaction

Every Host result is validated after the autonomous trajectory. The experiment
therefore measures whether stronger local autonomy can coexist with deterministic
boundary acceptance, rather than granting the Agent control of global program
continuation.

## Boundary contracts used by the implemented Workflow

The current bounded-autonomy Workflow declares both an Agent `input_schema`
and a structured result schema. Therefore the Host is free to change its internal
tool path, but it cannot receive structurally malformed task context through the
declared boundary, and its final result must satisfy the output contract before
the deterministic scenario validator is applied.
