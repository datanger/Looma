"""Prepare an isolated copy of the broken demo project."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"


def bump_counter(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(count + 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    repo = workdir / "project"
    workdir.mkdir(parents=True, exist_ok=True)
    bump_counter(workdir / ".counts" / "prepare.txt")

    created = False
    if not repo.exists():
        shutil.copytree(TEMPLATE, repo)
        created = True

    print(
        json.dumps(
            {
                "repo": str(repo),
                "created": created,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
