from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


METHODS = [
    "direct_sdk",
    "langgraph",
    "microsoft_agent_framework",
    "looma",
]


def load_sessions(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") == "valid" and "sus_score" in value:
            rows.append(value)
    return rows


def median(values):
    return statistics.median(values) if values else None


def mean(values):
    return statistics.mean(values) if values else None


def bootstrap_paired_delta(
    pairs: list[tuple[float, float]],
    *,
    samples: int,
    seed: int,
):
    if not pairs:
        return None
    observed = statistics.mean(right - left for left, right in pairs)
    rng = random.Random(seed)
    boot = []
    for _ in range(samples):
        sampled = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        boot.append(statistics.mean(right - left for left, right in sampled))
    boot.sort()
    low = boot[max(0, int(0.025 * (len(boot) - 1)))]
    high = boot[min(len(boot) - 1, int(0.975 * (len(boot) - 1)))]
    return {
        "mean_delta": round(observed, 4),
        "ci95_low": round(low, 4),
        "ci95_high": round(high, 4),
    }


def participant_pairs(rows, left_method, right_method, metric):
    by_participant: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_participant.setdefault(row["participant_id"], {})[row["method"]] = row

    pairs = []
    for methods in by_participant.values():
        if left_method in methods and right_method in methods:
            left = methods[left_method].get(metric)
            right = methods[right_method].get(metric)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                pairs.append((float(left), float(right)))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = load_sessions(args.sessions)
    aggregate = {}
    for method in METHODS:
        group = [row for row in rows if row["method"] == method]
        aggregate[method] = {
            "sessions": len(group),
            "completion_rate": round(
                sum(bool(row["tests_passed"]) for row in group) / len(group), 4
            ) if group else None,
            "median_elapsed_seconds": (
                round(median([row["elapsed_seconds"] for row in group]), 3)
                if group else None
            ),
            "median_implementation_sloc": (
                round(median([row["implementation_sloc"] for row in group]), 3)
                if group else None
            ),
            "median_debug_iterations": (
                round(median([row["debug_iterations"] for row in group]), 3)
                if group else None
            ),
            "median_documentation_lookups": (
                round(median([row["documentation_lookups"] for row in group]), 3)
                if group else None
            ),
            "mean_sus_score": (
                round(mean([row["sus_score"] for row in group]), 3)
                if group else None
            ),
        }

    comparisons = {}
    for method in METHODS:
        if method == "looma":
            continue
        comparisons[f"{method}_to_looma"] = {
            "elapsed_seconds_delta_looma_minus_baseline": bootstrap_paired_delta(
                participant_pairs(rows, method, "looma", "elapsed_seconds"),
                samples=args.bootstrap,
                seed=args.seed,
            ),
            "sus_delta_looma_minus_baseline": bootstrap_paired_delta(
                participant_pairs(rows, method, "looma", "sus_score"),
                samples=args.bootstrap,
                seed=args.seed + 1,
            ),
        }

    payload = {
        "schema": "aep-developer-study-summary-v1",
        "sessions": len(rows),
        "participants": len({row["participant_id"] for row in rows}),
        "aggregate": aggregate,
        "paired_comparisons": comparisons,
        "interpretation_guard": (
            "Do not claim shorter development time or better usability until "
            "prospective human sessions have been collected under the frozen protocol."
        ),
    }

    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
