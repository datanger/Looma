import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.workloads.adaptive_evidence.shared.backend import FixtureSemanticBackend
from experiments.workloads.adaptive_evidence.shared.workload import (
    evaluate_report, load_all_scenarios, public_scenario, validate_analysis, validate_evidence,
)


def test_fixture_backend_and_validators_cover_all_scenarios():
    for scenario in load_all_scenarios():
        public = public_scenario(scenario)
        backend = FixtureSemanticBackend(scenario["id"])
        evidence_check = {"status": "revise", "problems": ["not started"]}
        evidence = None
        for round_index in range(3):
            evidence = backend.research({"phase": "research", "round": round_index, "scenario": public, "problems": evidence_check["problems"]})
            evidence_check = validate_evidence(public, evidence)
            if evidence_check["status"] == "ready":
                break
        assert evidence_check["status"] == "ready"

        analysis_check = {"status": "revise", "problems": ["not started"]}
        analysis = None
        for round_index in range(3):
            analysis = backend.analyze({"phase": "analysis", "round": round_index, "scenario": public, "evidence": evidence, "problems": analysis_check["problems"]})
            analysis_check = validate_analysis(public, evidence, analysis)
            if analysis_check["status"] == "ready":
                break
        assert analysis_check["status"] == "ready"
        quality = evaluate_report(scenario, {"status": "complete", "analysis": analysis})
        assert quality["decision_correct"]
        assert quality["evidence_recall"] == 1.0
