"""Deterministically validate the semantic analysis before allowing a complete report."""

from __future__ import annotations

import argparse
import json
import re


REQUIRED_TRACKS = {
    "technical/K-line",
    "volume/turnover",
    "news/event",
    "risk/counter-evidence",
}

MARKET_FIELDS = ("open", "close", "high", "low", "volume", "turnover_rate_pct")


def _number_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", text))


def _grounded_market_evidence(evidence: list, rows: list[dict]) -> list[str]:
    grounded = []
    for statement in evidence:
        if not isinstance(statement, str):
            continue
        without_dates = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", statement)
        tokens = _number_tokens(without_dates)
        cited_rows = [
            row
            for row in rows
            if isinstance(row.get("date"), str) and row["date"] in statement
        ]
        if not cited_rows:
            continue
        explicit_claims = [
            (field, match.group(1))
            for field in MARKET_FIELDS
            for match in re.finditer(
                rf"\b{re.escape(field)}\s*[:=]\s*(-?\d+(?:\.\d+)?)",
                statement,
                flags=re.IGNORECASE,
            )
        ]
        if any(
            not any(
                field in row and format(float(row[field]), "g") == value
                for row in cited_rows
            )
            for field, value in explicit_claims
        ):
            continue
        source_values = {
            format(float(row[field]), "g")
            for row in cited_rows
            for field in MARKET_FIELDS
            if isinstance(row.get(field), (int, float))
            and not isinstance(row.get(field), bool)
        }
        if tokens and tokens.issubset(source_values):
            grounded.append(statement)
    return grounded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-json", required=True)
    parser.add_argument("--market-json", required=True)
    parser.add_argument("--news-json", required=True)
    args = parser.parse_args()

    analysis = json.loads(args.analysis_json)
    market = json.loads(args.market_json)
    news = json.loads(args.news_json)
    problems = []

    confidence = analysis.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        problems.append("confidence must be an integer between 0 and 100")

    tracks = set(analysis.get("analysis_tracks", []))
    missing_tracks = sorted(REQUIRED_TRACKS - tracks)
    if missing_tracks:
        problems.append("missing analysis tracks: " + ", ".join(missing_tracks))

    market_evidence = analysis.get("market_evidence", [])
    grounded_market_evidence = _grounded_market_evidence(
        market_evidence if isinstance(market_evidence, list) else [],
        market.get("rows", []),
    )
    if not grounded_market_evidence:
        problems.append(
            "market_evidence must include a source row date and matching numeric value; "
            "claims cannot be matched to market rows"
        )

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

    content_fields = (
        "technical_view",
        "volume_turnover_view",
        "news_event_view",
        "risk_counterevidence",
        "conclusion",
    )
    completed_content = sum(
        isinstance(analysis.get(field), str) and bool(analysis[field].strip())
        for field in content_fields
    )
    valid_news_citations = sum(url in known_news_urls for url in cited_news_urls)
    news_precision = (
        valid_news_citations / len(cited_news_urls)
        if cited_news_urls
        else (1.0 if not known_news_urls else 0.0)
    )
    scores = {
        "analysis_coverage": len(REQUIRED_TRACKS & tracks) / len(REQUIRED_TRACKS),
        "market_evidence_grounding": min(1.0, len(grounded_market_evidence) / 2),
        "news_evidence_precision": news_precision,
        "required_content": completed_content / len(content_fields),
    }

    print(json.dumps({
        "status": "ready" if not problems else "revise",
        "problems": problems,
        "scores": scores,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
