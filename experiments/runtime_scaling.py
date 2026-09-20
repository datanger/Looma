"""Measure Looma durable-history and guarded-resume overhead.

This is a runtime microbenchmark, not an Agent-quality benchmark. Agent output is
supplied deterministically so the result isolates Looma process/state/replay cost.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from experiments.common import (
    directory_bytes,
    latest_run,
    looma_env,
    only_request,
    read_json,
    run_python,
    write_json,
)


SCRIPT_TEMPLATE = r'''
from looma import agent, step, workflow

def identity(value):
    return {"value": value}

@workflow
def main():
    for i in range({events}):
        step(identity, i)
    result = agent(
        task="Return a deterministic benchmark acknowledgement.",
        input={{"events": {events}}},
        output_schema=dict,
    )
    print("BENCHMARK_DONE", result["ok"])

main()
'''


def run_once(events: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="looma-runtime-bench-") as raw:
        root = Path(raw)
        state_dir = root / "state"
        script = root / "workflow.py"
        script.write_text(SCRIPT_TEMPLATE.format(events=events), encoding="utf-8")
        env = looma_env(state_dir)

        started = time.perf_counter()
        first = run_python([script], cwd=root, env=env)
        first_ms = (time.perf_counter() - started) * 1000.0
        if first.returncode != 75:
            raise RuntimeError(
                f"initial run for events={events} returned {first.returncode}: "
                f"{first.stderr or first.stdout}"
            )

        run_dir = latest_run(state_dir)
        request_file = only_request(run_dir)
        request = read_json(request_file)
        result_file = Path(request["output"]["result_file"])
        write_json(result_file, {"ok": True})
        response_file = root / "agent2script.json"
        write_json(response_file, request["expected_output"])

        started = time.perf_counter()
        resumed = run_python(
            [
                "-m",
                "looma.cli",
                "handoff",
                "--request",
                request_file,
                "--response",
                response_file,
            ],
            cwd=root,
            env=env,
        )
        resume_ms = (time.perf_counter() - started) * 1000.0
        if resumed.returncode != 0:
            raise RuntimeError(
                f"guarded resume for events={events} returned {resumed.returncode}: "
                f"{resumed.stderr or resumed.stdout}"
            )

        state = read_json(run_dir / "state.json")
        if state["status"] != "completed":
            raise RuntimeError(f"workflow did not complete: {state['status']}")

        return {
            "events_requested": events,
            "durable_event_count": len(state["events"]),
            "initial_ms": round(first_ms, 3),
            "guarded_resume_ms": round(resume_ms, 3),
            "total_ms": round(first_ms + resume_ms, 3),
            "run_bytes": directory_bytes(run_dir),
            "state_json_bytes": (run_dir / "state.json").stat().st_size,
            "event_file_count": sum(
                1 for path in (run_dir / "events").iterdir() if path.is_file()
            ),
        }


def aggregate(rows: list[dict]) -> list[dict]:
    by_events: dict[int, list[dict]] = {}
    for row in rows:
        by_events.setdefault(row["events_requested"], []).append(row)

    output = []
    for events, group in sorted(by_events.items()):
        output.append(
            {
                "events_requested": events,
                "repeats": len(group),
                "initial_ms_median": round(
                    statistics.median(item["initial_ms"] for item in group), 3
                ),
                "guarded_resume_ms_median": round(
                    statistics.median(item["guarded_resume_ms"] for item in group), 3
                ),
                "total_ms_median": round(
                    statistics.median(item["total_ms"] for item in group), 3
                ),
                "run_bytes_median": int(
                    statistics.median(item["run_bytes"] for item in group)
                ),
                "state_json_bytes_median": int(
                    statistics.median(item["state_json_bytes"] for item in group)
                ),
            }
        )
    return output


def parse_events(value: str) -> list[int]:
    events = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not events or any(item < 0 for item in events):
        raise argparse.ArgumentTypeError("events must be a comma-separated list of non-negative integers")
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=parse_events, default=parse_events("10,100,1000"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be >= 1")

    rows = []
    for events in args.events:
        for repeat in range(args.repeats):
            row = run_once(events)
            row["repeat"] = repeat
            rows.append(row)

    payload = {
        "benchmark": "looma-runtime-scaling",
        "raw": rows,
        "aggregate": aggregate(rows),
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
