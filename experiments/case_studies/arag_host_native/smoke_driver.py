"""Deterministic integration smoke test for A-RAG tools + Looma boundaries.

This simulates a Host only for CI. It is not an Agent-quality experiment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.case_studies.arag_host_native.bridge import execute


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = Path(__file__).with_name("workflow.py")


def _latest_run(state_dir: Path) -> Path:
    return sorted(
        (state_dir / "runs").iterdir(),
        key=lambda path: path.stat().st_mtime_ns,
    )[-1]


def _pending_request(run_dir: Path) -> Path:
    for path in reversed(
        sorted((run_dir / "events").glob("*-script2agent.json"))
    ):
        request = json.loads(path.read_text(encoding="utf-8"))
        if not Path(request["output"]["result_file"]).exists():
            return path
    raise RuntimeError("no pending Agent request")


def run(config: str, session: str, question: str) -> int:
    with tempfile.TemporaryDirectory(prefix="looma-arag-smoke-") as raw:
        state_dir = Path(raw) / "state"
        env = os.environ.copy()
        env["LOOMA_STATE_DIR"] = str(state_dir)
        env["PYTHONPATH"] = (
            str(ROOT) + os.pathsep + str(ROOT / "src")
        )
        command = [
            sys.executable,
            str(WORKFLOW),
            "--question",
            question,
            "--config",
            config,
            "--session",
            session,
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        while result.returncode == 75:
            run_dir = _latest_run(state_dir)
            request_file = _pending_request(run_dir)
            request = json.loads(
                request_file.read_text(encoding="utf-8")
            )

            search = execute(
                config,
                session_path=session,
                tool_name="keyword_search",
                arguments={"keywords": ["Paris", "France"]},
                enable_semantic=False,
            )
            if search["metadata"].get("chunks_found", 0) < 1:
                raise RuntimeError("keyword_search found no evidence")

            execute(
                config,
                session_path=session,
                tool_name="read_chunk",
                arguments={"chunk_ids": ["0"]},
                enable_semantic=False,
            )

            business_result = {
                "answer": "Paris",
                "cited_chunk_ids": ["0"],
                "tool_path": ["keyword_search", "read_chunk"],
                "confidence": 100,
            }
            result_file = Path(
                request["output"]["result_file"]
            )
            result_file.write_text(
                json.dumps(
                    business_result,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            response_file = Path(raw) / "agent2script.json"
            response_file.write_text(
                json.dumps(
                    request["expected_output"],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "looma.cli",
                    "handoff",
                    "--request",
                    str(request_file),
                    "--response",
                    str(response_file),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.stdout.write(result.stdout)
        return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument(
        "--question",
        default="What is the capital of France?",
    )
    args = parser.parse_args()
    return run(
        args.config,
        args.session,
        args.question,
    )


if __name__ == "__main__":
    raise SystemExit(main())
