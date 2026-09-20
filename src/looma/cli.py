from __future__ import annotations

import argparse
import json
import shutil
from importlib.resources import files
from pathlib import Path


def _root(value: str | None) -> Path:
    return Path(value or ".looma").resolve()


def cmd_status(args: argparse.Namespace) -> int:
    root = _root(args.state_dir)
    runs = root / "runs"
    if not runs.exists():
        print("No Looma workflows found.")
        return 0
    rows = []
    for state_file in sorted(runs.glob("*/state.json")):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(
            {
                "run_id": state.get("run_id"),
                "workflow": state.get("workflow_name"),
                "status": state.get("status"),
                "events": len(state.get("events", [])),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    root = _root(args.state_dir)
    if not args.yes:
        raise SystemExit("Refusing to delete workflow state without --yes")
    if root.exists():
        shutil.rmtree(root)
    print(f"Removed {root}")
    return 0


def cmd_skill_path(args: argparse.Namespace) -> int:
    skill = files("looma").joinpath("skills", "llm-driven-programmatic-coding", "SKILL.md")
    print(str(skill))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="looma")
    parser.add_argument("--state-dir", default=None, help="State directory (default: .looma)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="List local workflow runs")
    p_status.set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset", help="Delete local workflow state")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    p_skill = sub.add_parser("skill-path", help="Print the bundled coding-agent Skill path")
    p_skill.set_defaults(func=cmd_skill_path)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
