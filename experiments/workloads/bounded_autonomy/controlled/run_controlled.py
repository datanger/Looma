"""RQ2 controlled programming-model comparison on the perturbation suite.

Runs every paradigm over the same scenarios with the same deterministic driver policy and
the same per-round action budget. The single difference is the action set each
application's orchestration declares:

* ``--routes dev``     the route set frozen after the development split;
* ``--routes widened`` the route set the held-out split turns out to need;
* AEP/Looma declares no action route at all — the Host owns it — so its command is
  identical in both batches, and the workflow file hash is recorded to prove it.

The reported quantity is adaptive task success rate (ATSR) per split, together with the
route gaps each split forces, the tool paths actually taken, and the SLOC of the declared
routes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from experiments.code_metrics import python_sloc
from experiments.workloads.bounded_autonomy.environment import load_scenarios, split_of
from experiments.workloads.bounded_autonomy.validator import score_result


BASE = Path(__file__).resolve().parent
# run_controlled.py -> controlled/ -> bounded_autonomy/ -> workloads/ -> experiments/ -> repo
ROOT = Path(__file__).resolve().parents[4]

PARADIGMS: dict[str, dict[str, Any]] = {
    "direct_sdk": {
        "label": "Direct SDK / hand-written loop",
        "entry": BASE / "direct_sdk" / "workflow.py",
        "accepts_routes": True,
        "code": {"dev": ["direct_sdk/workflow.py"], "widened": ["direct_sdk/workflow.py", "direct_sdk/widened.py"]},
    },
    "langgraph": {
        "label": "LangGraph StateGraph",
        "entry": BASE / "langgraph" / "workflow.py",
        "accepts_routes": True,
        "code": {"dev": ["langgraph/workflow.py"], "widened": ["langgraph/workflow.py", "langgraph/widened.py"]},
    },
    "microsoft_agent_framework": {
        "label": "Microsoft Agent Framework functional workflow",
        "entry": BASE / "microsoft_agent_framework" / "workflow.py",
        "accepts_routes": True,
        "code": {
            "dev": ["microsoft_agent_framework/workflow.py"],
            "widened": ["microsoft_agent_framework/workflow.py", "microsoft_agent_framework/widened.py"],
        },
    },
    "looma": {
        "label": "AEP / Looma (Host-native route)",
        "entry": BASE / "looma" / "host_driver.py",
        "accepts_routes": False,
        "code": {"dev": ["looma/workflow.py"], "widened": ["looma/workflow.py"]},
        "application_file": "looma/workflow.py",
        "host_file": "looma/host_driver.py",
    },
}

ROUTES_MODES = ("dev", "widened")
DEPENDENCY_HINTS = {
    "langgraph": "langgraph",
    "microsoft_agent_framework": "agent_framework",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_metrics(paradigm: str, routes_mode: str) -> dict[str, Any]:
    entry = PARADIGMS[paradigm]
    files = [BASE / name for name in entry["code"][routes_mode]]
    dev_files = [BASE / name for name in entry["code"]["dev"]]
    dev_sloc = sum(python_sloc(path) for path in dev_files)
    metrics = {
        "files": [str(path.relative_to(ROOT)) for path in files],
        "sloc": sum(python_sloc(path) for path in files),
        "dev_sloc": dev_sloc,
    }
    metrics["route_declaration_delta_sloc"] = metrics["sloc"] - dev_sloc
    application = entry.get("application_file")
    if application:
        metrics["application_sloc"] = python_sloc(BASE / application)
        metrics["application_sha256"] = file_hash(BASE / application)
    host = entry.get("host_file")
    if host:
        metrics["host_driver_sloc"] = python_sloc(BASE / host)
        metrics["host_driver_file"] = host
    return metrics


def framework_version(module_name: str) -> str | None:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    return str(getattr(module, "__version__", "unknown"))


def environment() -> dict[str, Any]:
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True
    )
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "commit": git.stdout.strip() or None,
        "worktree_dirty": bool((dirty.stdout or "").strip()),
        "langgraph_version": framework_version("langgraph"),
        "agent_framework_version": framework_version("agent_framework"),
    }


def run_one(paradigm: str, routes_mode: str, scenario: dict, raw_root: Path) -> dict[str, Any]:
    entry = PARADIGMS[paradigm]
    scenario_id = scenario["id"]
    output = raw_root / f"{paradigm}-{routes_mode}-{scenario_id}.json"
    command = [
        sys.executable, str(entry["entry"]),
        "--scenario", scenario_id, "--output", str(output),
    ]
    if entry["accepts_routes"]:
        command.extend(["--routes", routes_mode])

    env = {"PYTHONPATH": f"{ROOT}:{ROOT / 'src'}", "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

    row: dict[str, Any] = {
        "implementation": paradigm,
        "label": entry["label"],
        "routes_mode": routes_mode,
        "scenario_id": scenario_id,
        "split": split_of(scenario),
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        **code_metrics(paradigm, routes_mode),
    }

    if completed.returncode != 0 or not output.exists():
        stderr = completed.stderr or ""
        dependency = DEPENDENCY_HINTS.get(paradigm)
        if dependency and f"No module named '{dependency}'" in stderr:
            row.update({"status": "dependency_missing", "task_success": None,
                        "error": f"optional dependency {dependency!r} is not installed"})
            return row
        row.update({"status": "harness_error", "task_success": None, "error": stderr[-800:]})
        return row

    report = json.loads(output.read_text(encoding="utf-8"))
    host_trace = None
    host_file = Path(f"{output}.host.json")
    if host_file.exists():
        host_trace = json.loads(host_file.read_text(encoding="utf-8"))

    scored = score_result(scenario_id, report.get("result") or {"decision": None, "cited_source_ids": []})
    source = host_trace or report
    row.update(
        {
            "status": report["status"],
            "task_success": scored["task_success"],
            "decision_correct": scored["decision_correct"],
            "evidence_covered": scored["evidence_covered"],
            "gate_ready": scored["gate_ready"],
            "rounds": source.get("rounds"),
            "actions_used": source.get("actions_used"),
            "declared_actions": source.get("declared_actions"),
            "application_declared_actions": report.get("declared_actions"),
            "tool_path": source.get("tool_path"),
            "route_gaps": source.get("route_gaps") or [],
            "route_gap_actions": sorted({gap["action"] for gap in (source.get("route_gaps") or [])}),
            "error": None,
        }
    )
    return row


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for paradigm in PARADIGMS:
        for routes_mode in ROUTES_MODES:
            group = [
                row for row in rows
                if row["implementation"] == paradigm and row["routes_mode"] == routes_mode
            ]
            scored = [row for row in group if row.get("task_success") is not None]
            if not group:
                continue
            dev = [row for row in scored if row["split"] == "dev"]
            evaluation = [row for row in scored if row["split"] == "eval"]
            paths = {(tuple(row.get("tool_path") or [])) for row in scored}
            referenced = next((row for row in group if "sloc" in row), {})
            table.append(
                {
                    "implementation": paradigm,
                    "label": PARADIGMS[paradigm]["label"],
                    "routes_mode": routes_mode,
                    "sloc": referenced.get("sloc"),
                    "route_declaration_delta_sloc": referenced.get("route_declaration_delta_sloc"),
                    "application_sloc": referenced.get("application_sloc"),
                    "host_driver_sloc": referenced.get("host_driver_sloc"),
                    "scenarios_scored": len(scored),
                    "atsr_dev": round(sum(row["task_success"] for row in dev) / len(dev), 4) if dev else None,
                    "atsr_eval": round(sum(row["task_success"] for row in evaluation) / len(evaluation), 4) if evaluation else None,
                    "mean_actions": round(statistics.mean(row["actions_used"] for row in scored), 2) if scored else None,
                    "eval_route_gaps": sum(len(row["route_gaps"]) for row in evaluation),
                    "tool_path_diversity": len(paths),
                    "dependency_missing": any(row["status"] == "dependency_missing" for row in group),
                }
            )
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paradigms", default=",".join(PARADIGMS))
    parser.add_argument("--routes", default=",".join(ROUTES_MODES))
    parser.add_argument(
        "--allow-missing-dependencies",
        action="store_true",
        help="Record paradigms whose framework is not installed instead of failing the run.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paradigms = [item.strip() for item in args.paradigms.split(",") if item.strip()]
    unknown = [item for item in paradigms if item not in PARADIGMS]
    if unknown:
        parser.error(f"unknown paradigms: {', '.join(unknown)}")
    routes_modes = [item.strip() for item in args.routes.split(",") if item.strip()]

    scenarios = load_scenarios()
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="rq2-controlled-") as raw:
        raw_root = Path(raw)
        for paradigm in paradigms:
            for routes_mode in routes_modes:
                for scenario in scenarios:
                    rows.append(run_one(paradigm, routes_mode, scenario, raw_root))

    payload = {
        "benchmark": "rq2-controlled-perturbation",
        "mode": "deterministic-driver-policy-fixture",
        "note": (
            "Controlled orchestration comparison. The model is a deterministic driver "
            "policy shared by every paradigm, so these numbers measure route flexibility "
            "and orchestration overhead, not Agent output quality. Quality claims require "
            "the model-backed runs."
        ),
        "budget": {"max_rounds": 3, "max_actions_per_round": 12},
        "environment": environment(),
        "table": aggregate(rows),
        "rows": rows,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)

    harness_errors = [row for row in rows if row["status"] == "harness_error"]
    if harness_errors:
        return 2
    missing = sorted({row["implementation"] for row in rows if row["status"] == "dependency_missing"})
    if missing and not args.allow_missing_dependencies:
        print(
            "missing optional dependencies for: "
            + ", ".join(missing)
            + " (re-run with --allow-missing-dependencies to record them as unavailable)",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())