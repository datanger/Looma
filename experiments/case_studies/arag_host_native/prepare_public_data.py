from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from experiments.case_studies.arag_host_native.freeze_subset import (
    item_id,
    score,
)


DATASETS = ("musique", "hotpotqa", "2wikimultihop")
DEFAULT_REVISION = "b9198a5a8702cc35c6df7542529357a9af95d928"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze_subset(
    questions_file: Path,
    *,
    size: int,
    seed: str,
    output: Path,
) -> dict:
    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    ranked = sorted(
        (
            (score(seed, item_id(item, index)), index, item)
            for index, item in enumerate(questions)
        ),
        key=lambda row: (row[0], row[1]),
    )
    selected = ranked[: min(size, len(ranked))]
    subset = [item for _, _, item in selected]
    selected_ids = [
        item_id(item, original_index)
        for _, original_index, item in selected
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "selected_size": len(subset),
        "selected_qids": selected_ids,
        "sha256": sha256(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--subset-size", type=int, default=100)
    parser.add_argument("--seed", default="aep-paper-v1")
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    args = parser.parse_args()

    if args.subset_size < 1:
        parser.error("--subset-size must be >= 1")

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface_hub is required for public benchmark preparation"
        ) from exc

    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "aep-arag-public-data-v1",
        "repo_id": "Ayanami0730/rag_test",
        "revision": args.revision,
        "seed": args.seed,
        "subset_size": args.subset_size,
        "datasets": {},
    }

    for dataset in DATASETS:
        dataset_dir = root / dataset
        dataset_dir.mkdir(parents=True, exist_ok=True)

        records = {}
        for filename in ("questions.json", "chunks.json"):
            cached = Path(
                hf_hub_download(
                    repo_id="Ayanami0730/rag_test",
                    repo_type="dataset",
                    revision=args.revision,
                    filename=f"{dataset}/{filename}",
                )
            )
            target = dataset_dir / filename
            shutil.copyfile(cached, target)
            records[filename] = {
                "path": str(target),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }

        subset_path = dataset_dir / f"questions-dev{args.subset_size}.json"
        subset = freeze_subset(
            dataset_dir / "questions.json",
            size=args.subset_size,
            seed=f"{args.seed}:{dataset}",
            output=subset_path,
        )
        records["subset"] = {
            "path": str(subset_path),
            **subset,
        }
        manifest["datasets"][dataset] = records

    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
