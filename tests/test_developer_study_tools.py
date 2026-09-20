import json
import os
import subprocess
import sys
from pathlib import Path

from experiments.developer_study.make_assignments import balanced_latin_square
from experiments.developer_study.score_session import sus_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_module(*args: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_balanced_latin_square_contains_each_method_once_per_row():
    methods = ["a", "b", "c", "d"]
    square = balanced_latin_square(methods)
    assert len(square) == 4
    assert all(sorted(row) == sorted(methods) for row in square)


def test_standard_sus_scoring():
    assert sus_score([3] * 10) == 50.0
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0


def test_study_session_scoring_and_summary(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    base = {
        "participant_id": "P001",
        "task_id": "adaptive_evidence",
        "started_at": "2026-09-20T10:00:00Z",
        "ended_at": "2026-09-20T10:10:00Z",
        "tests_passed": True,
        "debug_iterations": 2,
        "documentation_lookups": 1,
        "external_help_events": 0,
        "sus_responses": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
    }

    for method, elapsed, sloc in (
        ("direct_sdk", 600, 80),
        ("looma", 420, 55),
    ):
        raw = tmp_path / f"{method}-raw.json"
        raw.write_text(
            json.dumps({
                **base,
                "method": method,
                "elapsed_seconds": elapsed,
                "implementation_sloc": sloc,
            }),
            encoding="utf-8",
        )
        scored = sessions / f"{method}.json"
        result = run_module(
            "-m",
            "experiments.developer_study.score_session",
            "--session",
            str(raw),
            "--output",
            str(scored),
        )
        assert result.returncode == 0, result.stderr

    summary = tmp_path / "summary.json"
    result = run_module(
        "-m",
        "experiments.developer_study.summarize",
        "--sessions",
        str(sessions),
        "--bootstrap",
        "100",
        "--output",
        str(summary),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["participants"] == 1
    assert payload["aggregate"]["looma"]["median_elapsed_seconds"] == 420
    delta = payload["paired_comparisons"]["direct_sdk_to_looma"][
        "elapsed_seconds_delta_looma_minus_baseline"
    ]
    assert delta["mean_delta"] == -180.0
