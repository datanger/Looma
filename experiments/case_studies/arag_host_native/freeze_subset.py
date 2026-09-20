from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def item_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("qid") or item.get("id") or index)


def score(seed: str, qid: str) -> str:
    return hashlib.sha256(f"{seed}\0{qid}".encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a deterministic A-RAG benchmark subset independent of source order."
    )
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--seed", default="aep-paper-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    if args.size < 1:
        parser.error("--size must be >= 1")

    raw = args.questions.read_bytes()
    questions = json.loads(raw.decode("utf-8"))
    if not isinstance(questions, list):
        parser.error("questions file must contain a JSON list")

    ranked = sorted(
        (
            (score(args.seed, item_id(item, index)), index, item)
            for index, item in enumerate(questions)
        ),
        key=lambda row: (row[0], row[1]),
    )
    selected = ranked[: min(args.size, len(ranked))]
    subset = [item for _, _, item in selected]
    selected_ids = [
        item_id(item, original_index)
        for _, original_index, item in selected
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema": "aep-arag-subset-v1",
        "source": str(args.questions),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "seed": args.seed,
        "requested_size": args.size,
        "selected_size": len(subset),
        "selected_qids": selected_ids,
        "subset_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
