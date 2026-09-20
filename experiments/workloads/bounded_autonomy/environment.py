from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SCENARIOS = HERE / "scenarios.json"


def load_scenarios() -> list[dict[str, Any]]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))


def load_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    raise KeyError(f"unknown scenario: {scenario_id}")


def public_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scenario["id"],
        "question": scenario["question"],
        "requirements": scenario["requirements"],
    }


def list_sources(scenario_id: str) -> dict[str, Any]:
    scenario = load_scenario(scenario_id)
    return {
        "sources": [
            {
                "id": source["id"],
                "kind": source["kind"],
                "available": source["available"],
                "authoritative": source["authoritative"],
            }
            for source in scenario["sources"]
        ]
    }


def read_source(scenario_id: str, source_id: str) -> dict[str, Any]:
    scenario = load_scenario(scenario_id)
    for source in scenario["sources"]:
        if source["id"] != source_id:
            continue
        if not source["available"]:
            return {
                "status": "unavailable",
                "source_id": source_id,
                "kind": source["kind"],
            }
        return {
            "status": "ready",
            "source_id": source_id,
            "kind": source["kind"],
            "authoritative": source["authoritative"],
            "content": source["content"],
        }
    return {"status": "not_found", "source_id": source_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    read = sub.add_parser("read")
    read.add_argument("--source", required=True)
    args = parser.parse_args()

    if args.command == "list":
        value = list_sources(args.scenario)
    else:
        value = read_source(args.scenario, args.source)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
