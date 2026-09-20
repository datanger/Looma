from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import string
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def qid(row: dict[str, Any], index: int) -> str:
    return str(row.get("qid") or row.get("id") or index)


def normalize_answer(value: Any) -> str:
    text = "" if value is None else str(value).lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def contain_correct(row: dict[str, Any]) -> int:
    pred = normalize_answer(row.get("pred_answer", ""))
    gold = normalize_answer(row.get("gold_answer") or row.get("answer", ""))
    return int(bool(pred and gold and gold in pred))


def answered(row: dict[str, Any]) -> int:
    value = row.get("pred_answer")
    return int(isinstance(value, str) and bool(value.strip()) and not value.startswith("Error:"))


def numeric(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def tool_calls(row: dict[str, Any]) -> int:
    logs = row.get("retrieval_logs")
    if isinstance(logs, list):
        return len(logs)
    path = row.get("tool_path")
    if isinstance(path, list):
        return len(path)
    trajectory = row.get("trajectory")
    if isinstance(trajectory, list):
        return sum(
            1
            for item in trajectory
            if isinstance(item, dict)
            and (
                "tool" in item
                or "tool_name" in item
                or item.get("type") in {"tool", "tool_call"}
            )
        )
    return 0


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def bootstrap_delta(
    pairs: list[tuple[float, float]],
    *,
    samples: int,
    seed: int,
) -> dict[str, float | None]:
    if not pairs:
        return {"delta": None, "ci95_low": None, "ci95_high": None}
    observed = statistics.mean(b - a for a, b in pairs)
    if len(pairs) == 1 or samples < 2:
        return {
            "delta": round(observed, 6),
            "ci95_low": round(observed, 6),
            "ci95_high": round(observed, 6),
        }

    rng = random.Random(seed)
    boot = []
    for _ in range(samples):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        boot.append(statistics.mean(b - a for a, b in sample))
    boot.sort()
    low_index = max(0, int(0.025 * (len(boot) - 1)))
    high_index = min(len(boot) - 1, int(0.975 * (len(boot) - 1)))
    return {
        "delta": round(observed, 6),
        "ci95_low": round(boot[low_index], 6),
        "ci95_high": round(boot[high_index], 6),
    }


def mean_available(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [value for row in rows if (value := numeric(row, key)) is not None]
    return round(statistics.mean(values), 6) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--aep", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline_rows = load_jsonl(args.baseline)
    aep_rows = load_jsonl(args.aep)
    baseline = {qid(row, i): row for i, row in enumerate(baseline_rows)}
    aep = {qid(row, i): row for i, row in enumerate(aep_rows)}
    common = sorted(set(baseline) & set(aep))
    missing_from_aep = sorted(set(baseline) - set(aep))
    missing_from_baseline = sorted(set(aep) - set(baseline))

    paired = []
    for key in common:
        left = baseline[key]
        right = aep[key]
        paired.append(
            {
                "qid": key,
                "baseline_contain": contain_correct(left),
                "aep_contain": contain_correct(right),
                "baseline_answered": answered(left),
                "aep_answered": answered(right),
                "baseline_retrieved_tokens": numeric(left, "total_retrieved_tokens"),
                "aep_retrieved_tokens": numeric(right, "total_retrieved_tokens"),
                "baseline_tool_calls": tool_calls(left),
                "aep_tool_calls": tool_calls(right),
                "baseline_llm_accuracy": numeric(left, "llm_accuracy"),
                "aep_llm_accuracy": numeric(right, "llm_accuracy"),
            }
        )

    contain_pairs = [
        (float(row["baseline_contain"]), float(row["aep_contain"]))
        for row in paired
    ]
    token_pairs = [
        (float(row["baseline_retrieved_tokens"]), float(row["aep_retrieved_tokens"]))
        for row in paired
        if row["baseline_retrieved_tokens"] is not None
        and row["aep_retrieved_tokens"] is not None
    ]
    tool_pairs = [
        (float(row["baseline_tool_calls"]), float(row["aep_tool_calls"]))
        for row in paired
    ]
    llm_pairs = [
        (float(row["baseline_llm_accuracy"]), float(row["aep_llm_accuracy"]))
        for row in paired
        if row["baseline_llm_accuracy"] is not None
        and row["aep_llm_accuracy"] is not None
    ]

    b = sum(
        row["baseline_contain"] == 1 and row["aep_contain"] == 0
        for row in paired
    )
    c = sum(
        row["baseline_contain"] == 0 and row["aep_contain"] == 1
        for row in paired
    )

    payload = {
        "schema": "aep-arag-paired-comparison-v1",
        "baseline": str(args.baseline),
        "aep": str(args.aep),
        "paired_questions": len(common),
        "missing_from_aep": missing_from_aep,
        "missing_from_baseline": missing_from_baseline,
        "baseline": {
            "answer_rate": round(
                sum(row["baseline_answered"] for row in paired) / len(paired),
                6,
            ) if paired else None,
            "contain_accuracy": round(
                sum(row["baseline_contain"] for row in paired) / len(paired),
                6,
            ) if paired else None,
            "avg_retrieved_tokens": mean_available(
                baseline_rows, "total_retrieved_tokens"
            ),
            "avg_tool_calls": round(
                statistics.mean(row["baseline_tool_calls"] for row in paired),
                6,
            ) if paired else None,
        },
        "aep": {
            "answer_rate": round(
                sum(row["aep_answered"] for row in paired) / len(paired),
                6,
            ) if paired else None,
            "contain_accuracy": round(
                sum(row["aep_contain"] for row in paired) / len(paired),
                6,
            ) if paired else None,
            "avg_retrieved_tokens": mean_available(
                aep_rows, "total_retrieved_tokens"
            ),
            "avg_tool_calls": round(
                statistics.mean(row["aep_tool_calls"] for row in paired),
                6,
            ) if paired else None,
        },
        "paired_deltas_aep_minus_baseline": {
            "contain_accuracy": bootstrap_delta(
                contain_pairs,
                samples=args.bootstrap,
                seed=args.seed,
            ),
            "retrieved_tokens": bootstrap_delta(
                token_pairs,
                samples=args.bootstrap,
                seed=args.seed + 1,
            ),
            "tool_calls": bootstrap_delta(
                tool_pairs,
                samples=args.bootstrap,
                seed=args.seed + 2,
            ),
            "llm_accuracy": bootstrap_delta(
                llm_pairs,
                samples=args.bootstrap,
                seed=args.seed + 3,
            ),
        },
        "mcnemar_contain": {
            "baseline_only_correct": b,
            "aep_only_correct": c,
            "exact_two_sided_p": round(exact_mcnemar(b, c), 8),
        },
        "paired": paired,
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
