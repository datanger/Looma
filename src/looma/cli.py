from __future__ import annotations

import argparse
import json
import shutil
from importlib.resources import files
from pathlib import Path

from .exceptions import Agent2ScriptValidationError
from .handoff import AGENT2SCRIPT_VALIDATION_EXIT_CODE, execute_validated_agent2script, format_agent2script_error


def _root(value: str | None) -> Path:
    return Path(value or ".looma").resolve()


def _state_files(root: Path) -> list[Path]:
    runs = root / "runs"
    if not runs.exists():
        return []
    return sorted(
        runs.glob("*/state.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _read_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cmd_status(args: argparse.Namespace) -> int:
    root = _root(args.state_dir)
    rows = []
    for state_file in _state_files(root):
        state = _read_state(state_file)
        if state is None:
            continue
        invocation = state.get("invocation") or {}
        rows.append(
            {
                "run_id": state.get("run_id"),
                "workflow": state.get("workflow_name"),
                "status": state.get("status"),
                "run_key": invocation.get("run_key"),
                "events": len(state.get("events", [])),
            }
        )

    if not rows:
        print("No Looma workflows found.")
        return 0

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    root = _root(args.state_dir)
    state_file: Path | None = None

    if args.run_id:
        candidate = root / "runs" / args.run_id / "state.json"
        if candidate.exists():
            state_file = candidate
        else:
            raise SystemExit(f"Looma run not found: {args.run_id}")
    else:
        files_found = _state_files(root)
        if not files_found:
            raise SystemExit("No Looma workflows found.")
        state_file = files_found[0]

    state = _read_state(state_file)
    if state is None:
        raise SystemExit(f"Could not read Looma state: {state_file}")

    events = []
    pending_request = None
    for event in state.get("events", []):
        item = {
            "index": event.get("index"),
            "kind": event.get("kind"),
            "status": event.get("status"),
            "key": event.get("key"),
            "result_file": event.get("result_file"),
        }
        request_file = event.get("request_file")
        if request_file:
            item["request_file"] = request_file
            request_path = Path(request_file)
            if request_path.exists():
                request = _read_state(request_path)
                if request is not None:
                    item["task"] = request.get("task")
                    item["expected_output"] = request.get("expected_output")
                    if event.get("status") == "waiting_agent":
                        pending_request = {
                            "request_file": request_file,
                            "result_file": (request.get("output") or {}).get("result_file"),
                            "output_schema": (request.get("output") or {}).get("output_schema"),
                            "expected_output": request.get("expected_output"),
                        }
        events.append(item)

    payload = {
        "run_id": state.get("run_id"),
        "workflow": state.get("workflow_name"),
        "status": state.get("status"),
        "source_function": state.get("source_function"),
        "invocation": state.get("invocation"),
        "error": state.get("error"),
        "pending_request": pending_request,
        "events": events,
        "state_file": str(state_file),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    skill = files("looma").joinpath("skills", "agent-embedded-programming", "SKILL.md")
    print(str(skill))
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    try:
        return execute_validated_agent2script(
            request_file=args.request,
            response_file=args.response,
        )
    except Agent2ScriptValidationError as exc:
        print(format_agent2script_error(exc))
        return AGENT2SCRIPT_VALIDATION_EXIT_CODE


def main() -> int:
    parser = argparse.ArgumentParser(prog="looma")
    parser.add_argument("--state-dir", default=None, help="State directory (default: .looma)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="List local workflow runs")
    p_status.set_defaults(func=cmd_status)

    p_inspect = sub.add_parser("inspect", help="Inspect one workflow run (latest by default)")
    p_inspect.add_argument("run_id", nargs="?", default=None)
    p_inspect.set_defaults(func=cmd_inspect)

    p_reset = sub.add_parser("reset", help="Delete local workflow state")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    p_skill = sub.add_parser(
        "skill-path",
        help="Print the bundled Agent-Embedded Programming Skill path",
    )
    p_skill.set_defaults(func=cmd_skill_path)

    p_handoff = sub.add_parser(
        "handoff",
        help="Validate Agent result and agent2script, then resume the workflow",
    )
    p_handoff.add_argument("--request", required=True, help="Path to the persisted script2agent JSON")
    p_handoff.add_argument("--response", required=True, help="Path to the Agent-returned agent2script JSON")
    p_handoff.set_defaults(func=cmd_handoff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
