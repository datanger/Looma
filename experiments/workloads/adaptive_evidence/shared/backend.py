from __future__ import annotations

from typing import Any

from .workload import load_scenario, source_map


class FixtureSemanticBackend:
    """Deterministic semantic backend for orchestration/CI experiments only."""

    def __init__(self, scenario_id: str):
        self.scenario = load_scenario(scenario_id)
        self.sources = source_map(self.scenario)

    def research(self, payload: dict[str, Any]) -> dict[str, Any]:
        round_index = int(payload.get("round", 0))
        rounds = self.scenario["fixture"]["research_rounds"]
        source_ids = rounds[min(round_index, len(rounds) - 1)]
        evidence = [
            {"source_id": source_id, "claim": self.sources[source_id]["content"]}
            for source_id in source_ids
        ]
        return {
            "evidence": evidence,
            "actions": [f"inspect:{source_id}" for source_id in source_ids],
            "coverage_note": f"fixture research round {round_index}",
        }

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        round_index = int(payload.get("round", 0))
        rounds = self.scenario["fixture"]["analysis_rounds"]
        return dict(rounds[min(round_index, len(rounds) - 1)])

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        phase = payload.get("phase")
        if phase == "research":
            return self.research(payload)
        if phase == "analysis":
            return self.analyze(payload)
        raise ValueError(f"unknown semantic phase: {phase}")
