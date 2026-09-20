"""Run the complete multi-stage Looma workflow with Codex as the host Agent.

Requires a locally installed and authenticated Codex CLI. The workflow itself
does not contain an LLM API client.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--state-dir", default=None)
    args = parser.parse_args()

    codex = shutil.which("codex")
    if not codex:
        raise SystemExit(
            "Codex CLI was not found in PATH. Install Codex CLI and authenticate "
            "with your ChatGPT/Codex account before running this E2E example."
        )

    workdir = Path(args.workdir).resolve()
    state_dir = Path(args.state_dir or (workdir / ".looma-state")).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    workflow = HERE / "workflow.py"
    prompt = f"""
You are the host Coding Agent for a Looma end-to-end test.

Repository: {REPO_ROOT}
Workflow command:
LOOMA_STATE_DIR={state_dir} python {workflow} --workdir {workdir}

Execute the complete workflow yourself using terminal commands.

Rules:
1. Start by running the workflow command exactly as shown.
2. When Looma exits with code 75, read the emitted SCRIPT2AGENT payload and
   LOOMA_REQUEST_FILE.
3. Complete the task described by that SCRIPT2AGENT request.
4. Write ONLY the business result JSON required by output.output_schema to
   output.result_file.
5. Save the returned agent2script JSON to a temporary response file. It must
   contain only script and args and must exactly equal expected_output.
6. Resume ONLY through:
   looma handoff --request <LOOMA_REQUEST_FILE> --response <response-file>
7. If handoff returns 75, repeat the same process for the next Agent boundary.
8. Never bypass looma handoff and never directly execute an unvalidated
   agent2script command.
9. Continue until the workflow exits with code 0.
10. At the end verify {workdir / "final.json"} exists and print a concise
    completion summary.

For this deterministic demo:
- Agent #1 should choose strategy "aggressive".
- Agent #2 should return approved=true and route="summary".
""".strip()

    completed = subprocess.run(
        [
            codex,
            "exec",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            prompt,
        ],
        cwd=REPO_ROOT,
        text=True,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
