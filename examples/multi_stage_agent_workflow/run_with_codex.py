"""Run the complete multi-stage Looma workflow with Codex as the host Agent.

Requires a locally installed and authenticated Codex CLI. The workflow itself
does not contain an LLM API client.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_WORKDIR = REPO_ROOT / ".looma-codex-e2e"


def _require_repo_local(path: Path, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SystemExit(
            f"{name} must be inside the repository when using Codex "
            f"workspace-write sandbox: {resolved}"
        ) from exc
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--state-dir", default=None)
    args = parser.parse_args()

    codex = shutil.which("codex")
    if not codex:
        raise SystemExit(
            "Codex CLI was not found in PATH. Install Codex CLI and authenticate "
            "with your ChatGPT/Codex account before running this E2E example."
        )

    workdir = _require_repo_local(Path(args.workdir), "workdir")
    state_dir = _require_repo_local(
        Path(args.state_dir) if args.state_dir else workdir / ".looma-state",
        "state-dir",
    )
    workdir.mkdir(parents=True, exist_ok=True)

    workflow = HERE / "workflow.py"
    python = Path(sys.executable).resolve()
    pythonpath = REPO_ROOT / "src"

    workflow_command = (
        f"PYTHONPATH={pythonpath} LOOMA_STATE_DIR={state_dir} "
        f"{python} {workflow} --workdir {workdir}"
    )
    handoff_command = (
        f"PYTHONPATH={pythonpath} {python} -m looma.cli handoff "
        "--request <LOOMA_REQUEST_FILE> --response <response-file>"
    )

    prompt = f"""
You are the host Coding Agent for a Looma end-to-end test.

Repository: {REPO_ROOT}

Execute this complete workflow yourself using terminal commands.

Initial workflow command:
{workflow_command}

Rules:
1. Start by running the initial workflow command exactly as shown.
2. When Looma exits with code 75, read the emitted SCRIPT2AGENT payload and
   LOOMA_REQUEST_FILE.
3. Complete the task described by that SCRIPT2AGENT request.
4. Write ONLY the business result JSON required by output.output_schema to
   output.result_file.
5. Save agent2script to a response JSON file. It must contain only script and
   args and must exactly equal expected_output.
6. Resume ONLY through this command shape:
   {handoff_command}
7. If handoff returns 75, repeat the same process for the next Agent boundary.
8. Never bypass looma handoff and never directly execute an unvalidated
   agent2script command.
9. Continue until the workflow exits with code 0.
10. Verify {workdir / "final.json"} exists.
11. Verify every *.count file in {workdir} contains exactly 1, proving replay
    did not re-execute completed scripts.
12. Print a concise completion summary only after all checks pass.

For this deterministic E2E:
- Agent #1 must choose strategy "aggressive".
- Agent #2 must return approved=true and route="summary".
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
