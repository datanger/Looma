# Multi-script workflow

This example demonstrates a Looma workflow composed from **multiple standalone Python scripts** plus an embedded host Agent decision.

The workflow is:

```text
workflow.py
   │
   ├─ step → collect.py
   │            ↓
   │         raw.json
   │
   ├─ step → transform.py
   │            ↓
   │       processed.json
   │
   ├─ agent(...)
   │            ↓
   │      choose report mode
   │
   └─ step → report.py
                ↓
            report.json
```

The scripts are intentionally separate processes. Looma keeps the orchestration in ordinary Python and wraps each external script invocation in `step()`, so completed scripts are not re-executed during replay after the Agent boundary.

Run:

```bash
python examples/multi_script_workflow/workflow.py --workdir /tmp/looma-multi-script
```

On the first run, `collect.py` and `transform.py` execute, then `agent()` suspends the workflow. After the host Agent writes the result and resumes the original command, Looma replays the first two steps from history and continues with `report.py`.

This pattern is useful when an existing engineering flow already consists of independent scripts or tools and you want to insert Agent decisions between them without rewriting everything into one process.
