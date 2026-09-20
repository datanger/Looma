import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_experiment(*args: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_reliability_fault_harness_smoke(tmp_path: Path):
    output = tmp_path / "reliability.json"
    result = run_experiment(
        "-m",
        "experiments.reliability_faults",
        "--cases",
        "valid,missing_result,wrong_result_schema,wrong_resume_args",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["cases"] == 4
    assert payload["summary"]["false_acceptances"] == 0
    assert payload["summary"]["valid_completions"] == 1


def test_runtime_scaling_harness_smoke(tmp_path: Path):
    output = tmp_path / "runtime.json"
    result = run_experiment(
        "-m",
        "experiments.runtime_scaling",
        "--events",
        "2",
        "--repeats",
        "1",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["raw"][0]
    assert row["events_requested"] == 2
    assert row["durable_event_count"] == 3
    assert row["run_bytes"] > 0


def test_code_metrics_harness_smoke(tmp_path: Path):
    output = tmp_path / "metrics.json"
    result = run_experiment(
        "-m",
        "experiments.code_metrics",
        f"runtime={PROJECT_ROOT / 'src' / 'looma' / 'runtime.py'}",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["implementations"]["runtime"]["python_files"] == 1
    assert payload["implementations"]["runtime"]["sloc"] > 0
