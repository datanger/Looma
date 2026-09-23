"""RQ2 retrieval-perturbation runner on public multi-hop QA instances.

Every task instance is a public benchmark item (pinned A-RAG revision); the only
thing authored here is the deterministic perturbation transform and the harness
that measures it. See `research/RETRIEVAL_PERTURBATION_PROTOCOL.md`.

The runner builds each instance in process, writes the **gold-free** payload the
paradigms are allowed to read, executes every paradigm over the same instances
with the same driver and budget, and scores the outcome from the gold-bearing
environment it kept to itself.
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
from experiments.workloads.retrieval_perturbation.injectors import (
    EVAL_PERTURBATIONS,
    PERTURBATIONS,
)
from experiments.workloads.retrieval_perturbation.instance import (
    DEFAULT_SEED,
    Instance,
    select_instances,
    write_payload,
)
from experiments.workloads.retrieval_perturbation.protocol import score_result

BASE = Path(__file__).resolve().parent
# run_perturbation.py -> retrieval_perturbation/ -> workloads/ -> experiments/ -> repo
ROOT = Path(__file__).resolve().parents[3]

PUBLIC_DATASETS = ("musique", "hotpotqa", "2wikimultihop")

PARADIGMS: dict[str, dict[str, Any]] = {
    "direct_sdk": {
        "label": "Direct SDK / hand-written retrieval loop",
        "entry": BASE / "direct_sdk" / "workflow.py",
        "accepts_routes": True,
        "code": {
            "dev": ["direct_sdk/workflow.py"],
            "widened": ["direct_sdk/workflow.py", "direct_sdk/widened.py"],
        },
    },
    "looma": {
        "label": "AEP / Looma (Host-native retrieval route)",
        "entry": BASE / "looma" / "host_driver.py",
        "accepts_routes": False,
        "code": {"dev": ["looma/workflow.py"], "widened": ["looma/workflow.py"]},
        "host_file": "looma/host_driver.py",
    },
}

ROUTES_MODES = ("dev", "widened")
DEPENDENCY_HINTS: dict[str, str] = {}


def dataset_mode(data_root: Path, dataset: str) -> str:
    """`public` only for the pinned benchmark datasets; everything else is a fixture."""
    if (data_root / dataset / "fixture").exists():
        return "fixture"
    if dataset in PUBLIC_DATASETS:
        return "public"
    return "fixture"


def code_metrics(paradigm: str, routes_mode: str) -> dict[str, Any]:
    entry = PARADIGMS[paradigm]
    files = [BASE / name for name in entry["code"][routes_mode]]
    dev_files = [BASE / name for name in entry["code"]["dev"]]
    dev_sloc = sum(python_sloc(path) for path in dev_files)
    # The application is exactly the set of files that had to be written for that
    # route mode. The Host simulator is never part of it, which is what makes the
    # two paradigms comparable on the same axis.
    application_bytes = b"".join(path.read_bytes() for path in files)
    metrics: dict[str, Any] = {
        "files": [str(path.relative_to(ROOT)) for path in files],
        "sloc": sum(python_sloc(path) for path in files),
        "dev_sloc": dev_sloc,
        "application_sloc": sum(python_sloc(path) for path in files),
        "application_sha256": hashlib.sha256(application_bytes).hexdigest(),
    }
    metrics["route_declaration_delta_sloc"] = metrics["sloc"] - dev_sloc
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
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True)
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "commit": git.stdout.strip() or None,
        "worktree_dirty": bool((dirty.stdout or "").strip()),
        "langgraph_version": framework_version("langgraph"),
        "agent_framework_version": framework_version("agent_framework"),
    }


def run_one(
    paradigm: str,
    routes_mode: str,
    instance: Instance,
    payload_file: Path,
    work_root: Path,
) -> dict[str, Any]:
    entry = PARADIGMS[paradigm]
    key = instance.instance_id.replace(":", "-") + f"-{paradigm}-{routes_mode}"
    output = work_root / f"{key}.json"
    session_file = work_root / f"{key}.session.json"

    command = [
        sys.executable, str(entry["entry"]),
        "--instance", str(payload_file),
        "--output", str(output),
        "--session", str(session_file),
    ]
    if entry["accepts_routes"]:
        command.extend(["--routes", routes_mode])

    env = {
        "PYTHONPATH": f"{ROOT}:{ROOT / 'src'}",
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(Path.home()),
    }
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

    row: dict[str, Any] = {
        "implementation": paradigm,
        "label": entry["label"],
        "routes_mode": routes_mode,
        "dataset": instance.environment.dataset,
        "qid": instance.environment.qid,
        "perturbation": instance.environment.perturbation,
        "split": instance.split,
        "instance_id": instance.instance_id,
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        **code_metrics(paradigm, routes_mode),
    }

    if completed.returncode != 0 or not output.exists():
        stderr = completed.stderr or ""
        dependency = DEPENDENCY_HINTS.get(paradigm)
        if dependency and f"No module named '{dependency}'" in stderr:
            row.update({
                "status": "dependency_missing",
                "adaptive_success": None,
                "error": f"optional dependency {dependency!r} is not installed",
            })
            return row
        row.update({"status": "harness_error", "adaptive_success": None, "error": stderr[-800:]})
        return row

    report = json.loads(output.read_text(encoding="utf-8"))
    host_file = Path(f"{output}.host.json")
    host_trace = json.loads(host_file.read_text(encoding="utf-8")) if host_file.exists() else None
    result = report.get("result") or {"status": "insufficient", "answer": "", "cited_chunk_ids": []}
    scored = score_result(instance.environment, result)
    source = host_trace or report

    route_gaps = source.get("route_gaps") or []
    row.update({
        "status": report["status"],
        "rounds": source.get("rounds"),
        "actions_used": source.get("actions_used"),
        "declared_actions": source.get("declared_actions"),
        "application_declared_actions": report.get("declared_actions"),
        "environment_actions": source.get("environment_actions") or report.get("environment_actions"),
        "tool_path": source.get("tool_path"),
        "route_gaps": route_gaps,
        "route_gap_actions": sorted({gap["action"] for gap in route_gaps}),
        "gate_ready": (report.get("validation") or {}).get("status") == "ready",
        "error": None,
        **scored,
    })
    return row


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    keys = sorted({(row["implementation"], row["routes_mode"], row["dataset"]) for row in rows})
    for paradigm, routes_mode, dataset in keys:
        group = [
            row for row in rows
            if (row["implementation"], row["routes_mode"], row["dataset"])
            == (paradigm, routes_mode, dataset)
        ]
        scored = [row for row in group if row.get("adaptive_success") is not None]
        answerable = [row for row in scored if row["answerable"]]
        unanswerable = [row for row in scored if not row["answerable"]]
        dev = [row for row in answerable if row["split"] == "dev"]
        evaluation = [row for row in answerable if row["split"] == "eval"]
        referenced = next((row for row in group if "sloc" in row), {})

        def rate(items: list[dict[str, Any]], field: str) -> float | None:
            if not items:
                return None
            return round(sum(bool(row[field]) for row in items) / len(items), 4)

        table.append({
            "implementation": paradigm,
            "label": PARADIGMS[paradigm]["label"],
            "routes_mode": routes_mode,
            "dataset": dataset,
            "sloc": referenced.get("sloc"),
            "route_declaration_delta_sloc": referenced.get("route_declaration_delta_sloc"),
            "application_sloc": referenced.get("application_sloc"),
            "host_driver_sloc": referenced.get("host_driver_sloc"),
            "application_sha256": referenced.get("application_sha256"),
            "instances_scored": len(scored),
            "answerable_instances": len(answerable),
            "unanswerable_instances": len(unanswerable),
            "adaptive_success_dev": rate(dev, "adaptive_success"),
            "adaptive_success_eval": rate(evaluation, "adaptive_success"),
            "adaptive_success_overall": rate(answerable, "adaptive_success"),
            "correct_refusal_rate": rate(unanswerable, "adaptive_success"),
            "false_answers": sum(bool(row["false_answer"]) for row in scored),
            "gate_ready_rate": rate(scored, "gate_ready"),
            "mean_evidence_recall": (
                round(statistics.mean(row["evidence_recall"] for row in answerable), 4)
                if answerable else None
            ),
            "mean_actions": (
                round(statistics.mean(row["actions_used"] or 0 for row in scored), 2) if scored else None
            ),
            "eval_route_gaps": sum(len(row["route_gaps"]) for row in evaluation),
            "eval_instances_with_route_gap": sum(1 for row in evaluation if row["route_gaps"]),
            "tool_path_diversity": len({tuple(row.get("tool_path") or []) for row in scored}),
            "evidence_mode": next((row.get("evidence_mode") for row in scored), None),
            "dependency_missing": any(row["status"] == "dependency_missing" for row in group),
        })
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--datasets", default=",".join(PUBLIC_DATASETS))
    parser.add_argument("--perturbations", default=",".join(PERTURBATIONS))
    parser.add_argument("--limit", type=int, default=None, help="questions per dataset")
    parser.add_argument("--paradigms", default=",".join(PARADIGMS))
    parser.add_argument("--routes", default=",".join(ROUTES_MODES))
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument(
        "--expect-public",
        action="store_true",
        help="Refuse to run on anything that is not a pinned public benchmark dataset.",
    )
    parser.add_argument("--allow-missing-dependencies", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    datasets = [item.strip() for item in args.datasets.split(",") if item.strip()]
    perturbations = tuple(item.strip() for item in args.perturbations.split(",") if item.strip())
    unknown = [item for item in perturbations if item not in PERTURBATIONS]
    if unknown:
        parser.error(f"unknown perturbations: {', '.join(unknown)}")
    paradigms = [item.strip() for item in args.paradigms.split(",") if item.strip()]
    wrong = [item for item in paradigms if item not in PARADIGMS]
    if wrong:
        parser.error(f"unknown paradigms: {', '.join(wrong)}")
    routes_modes = [item.strip() for item in args.routes.split(",") if item.strip()]

    modes = {dataset: dataset_mode(args.data_root, dataset) for dataset in datasets}
    if args.expect_public:
        bad = [dataset for dataset, mode in modes.items() if mode != "public"]
        if bad:
            parser.error(
                "not a pinned public benchmark dataset: " + ", ".join(bad)
            )

    rows: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rq2-retrieval-") as raw:
        work_root = Path(raw)
        for dataset in datasets:
            instances = select_instances(
                args.data_root,
                dataset,
                perturbations=perturbations,
                limit=args.limit,
                seed=args.seed,
            )
            provenance[dataset] = {
                "mode": modes[dataset],
                "questions_file": instances[0].corpus.sources["questions"],
                "chunks_file": instances[0].corpus.sources["chunks"],
                "corpus_shape": instances[0].corpus.shape,
                "instances": len(instances),
                "unanswerable_instances": sum(
                    1 for item in instances if not item.environment.evidence_present
                ),
            }
            for instance in instances:
                payload_file = work_root / f"{instance.instance_id.replace(':', '-')}.instance.json"
                write_payload(instance, payload_file)
                for paradigm in paradigms:
                    for routes_mode in routes_modes:
                        rows.append(
                            run_one(paradigm, routes_mode, instance, payload_file, work_root)
                        )

    fixture_only = all(mode == "fixture" for mode in modes.values())
    payload = {
        "benchmark": "rq2-retrieval-perturbation",
        "mode": "fixture" if fixture_only else "public",
        "data_root": str(args.data_root),
        "seed": args.seed,
        "note": (
            "Controlled RQ2 comparison re-based on public multi-hop QA instances. The "
            "model is a deterministic retrieval driver shared by every paradigm, so "
            "these numbers measure route flexibility and evidence reach, not answer "
            "quality. Answer-level accuracy requires model-backed Host-native runs. "
            "The perturbation transform, the tool surface, the gate and the scoring are "
            "ours; no question, gold answer or paragraph is."
        ),
        "budget": {"max_rounds": 2, "max_actions_per_round": 12},
        "environment": environment(),
        "provenance": provenance,
        "eval_perturbations": list(EVAL_PERTURBATIONS),
        "table": aggregate(rows),
        "rows": rows,
    }
    if fixture_only:
        payload["fixture_warning"] = (
            "Ran on a fixture corpus in the public files' shape. These numbers verify "
            "control flow only and must never appear in a results table."
        )
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
            "missing optional dependencies for: " + ", ".join(missing)
            + " (re-run with --allow-missing-dependencies to record them as unavailable)",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())