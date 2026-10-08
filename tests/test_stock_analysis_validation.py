import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PROJECT_ROOT / "examples" / "stock_analysis_agent" / "validate_analysis.py"


def _analysis() -> dict:
    return {
        "analysis_tracks": [
            "technical/K-line",
            "volume/turnover",
            "news/event",
            "risk/counter-evidence",
        ],
        "market_evidence": [
            "2026-09-09 close=210 volume=120",
            "2026-09-10 close=214 turnover_rate=4.4%",
        ],
        "news_evidence_urls": ["https://example.test/news"],
        "confidence": 70,
        "technical_view": "Trend is positive.",
        "volume_turnover_view": "Volume expanded.",
        "news_event_view": "The event is recent.",
        "risk_counterevidence": "The sample is short.",
        "conclusion": "Evidence is mixed.",
    }


def _validate(tmp_path: Path, analysis: dict) -> dict:
    market = {
        "rows": [
            {
                "date": "2026-09-09",
                "open": 208,
                "close": 210,
                "high": 212,
                "low": 205,
                "volume": 120,
                "turnover_rate_pct": 4.2,
            },
            {
                "date": "2026-09-10",
                "open": 212,
                "close": 214,
                "high": 216,
                "low": 210,
                "volume": 130,
                "turnover_rate_pct": 4.4,
            },
        ]
    }
    news = {"items": [{"url": "https://example.test/news"}]}
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--analysis-json",
            json.dumps(analysis),
            "--market-json",
            json.dumps(market),
            "--news-json",
            json.dumps(news),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_validator_scores_grounded_evidence_and_analysis_coverage(tmp_path: Path):
    result = _validate(tmp_path, _analysis())

    assert result["status"] == "ready"
    assert result["scores"] == {
        "analysis_coverage": 1.0,
        "market_evidence_grounding": 1.0,
        "news_evidence_precision": 1.0,
        "required_content": 1.0,
    }


def test_validator_rejects_market_claim_not_found_in_source_rows(tmp_path: Path):
    analysis = _analysis()
    analysis["market_evidence"] = [
        "2026-09-09 close=210 close=999 volume=120"
    ]

    result = _validate(tmp_path, analysis)

    assert result["status"] == "revise"
    assert any("cannot be matched" in problem for problem in result["problems"])
    assert result["scores"]["market_evidence_grounding"] == 0.0
