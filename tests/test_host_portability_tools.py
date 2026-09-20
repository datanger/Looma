import json
import os
import subprocess
import sys
from pathlib import Path


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


def test_host_portability_manifest_and_compare(tmp_path: Path):
    workflow = tmp_path / "workflow.py"
    workflow.write_text("print('same workflow')\n", encoding="utf-8")

    manifests = []
    for host in ("host-a", "host-b"):
        results = tmp_path / f"{host}.json"
        results.write_text(
            json.dumps({"status": "complete", "host": host}),
            encoding="utf-8",
        )
        metrics = tmp_path / f"{host}-metrics.json"
        metrics.write_text(
            json.dumps({"task_success_rate": 1.0}),
            encoding="utf-8",
        )
        manifest = tmp_path / f"{host}-manifest.json"
        result = run_module(
            "-m",
            "experiments.host_portability.record_run",
            "--host",
            host,
            "--host-version",
            "1",
            "--model",
            "test-model",
            "--workflow",
            str(workflow),
            "--results",
            str(results),
            "--metrics",
            str(metrics),
            "--output",
            str(manifest),
        )
        assert result.returncode == 0, result.stderr
        manifests.append(manifest)

    comparison = tmp_path / "comparison.json"
    result = run_module(
        "-m",
        "experiments.host_portability.compare_runs",
        *(str(path) for path in manifests),
        "--output",
        str(comparison),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(comparison.read_text(encoding="utf-8"))
    assert payload["same_workflow"] is True
    assert payload["run_count"] == 2
