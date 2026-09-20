"""Deterministically validate the semantic analysis before allowing a complete report."""

from __future__ import annotations

import argparse
import json


REQUIRED_TRACKS = {
    "technical/K-line",
    "volume/turnover",
    "news/event",
    "risk/counter-evidence",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-json", required=True)
    parser.add_argument("--news-json", required=True)
    args = parser.parse_args()

    analysis = json.loads(args.analysis_json)
    news = json.loads(args.news_json)
    problems = []

    confidence = analysis.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        problems.append("confidence must be an integer between 0 and 100")

    tracks = set(analysis.get("analysis_tracks", []))
    missing_tracks = sorted(REQUIRED_TRACKS - tracks)
    if missing_tracks:
        problems.append("missing analysis tracks: " + ", ".join(missing_tracks))

    if not analysis.get("market_evidence"):
        problems.append("market_evidence must cite concrete market observations")

    known_news_urls = {item.get("url") for item in news.get("items", []) if item.get("url")}
    cited_news_urls = analysis.get("news_evidence_urls", [])
    unknown_urls = [url for url in cited_news_urls if url not in known_news_urls]
    if unknown_urls:
        problems.append("news_evidence_urls contains URLs not present in recent_news")

    if known_news_urls and not cited_news_urls:
        problems.append("news_evidence_urls must cite at least one provided recent-news item")

    for field in (
        "technical_view",
        "volume_turnover_view",
        "news_event_view",
        "risk_counterevidence",
        "conclusion",
    ):
        value = analysis.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} must be non-empty")

    print(json.dumps({
        "status": "ready" if not problems else "revise",
        "problems": problems,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
