"""Deterministically check whether market and recent-news evidence is usable."""

from __future__ import annotations

import argparse
import json
from datetime import datetime


def parse_day(value: str):
    return datetime.fromisoformat(value[:10]).date()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-json", required=True)
    parser.add_argument("--market-json", required=True)
    parser.add_argument("--news-json", required=True)
    args = parser.parse_args()

    target = json.loads(args.target_json)
    market = json.loads(args.market_json)
    news = json.loads(args.news_json)

    problems = []

    if len(market.get("rows", [])) < 5:
        problems.append("market data has fewer than 5 trading rows")

    if news.get("window_start") != target["news_start"] or news.get("window_end") != target["news_end"]:
        problems.append("news research window does not match workflow window")

    if not news.get("search_queries"):
        problems.append("news research did not record search queries")

    if len(news.get("searched_sources", [])) < 2:
        problems.append("news research covered fewer than two sources")

    start = parse_day(target["news_start"])
    end = parse_day(target["news_end"])

    invalid_items = []
    for index, item in enumerate(news.get("items", [])):
        for key in ("published_at", "title", "source", "url", "summary"):
            if not item.get(key):
                invalid_items.append({"index": index, "reason": f"missing {key}"})
                break
        else:
            try:
                published = parse_day(item["published_at"])
            except Exception:
                invalid_items.append({"index": index, "reason": "invalid published_at"})
                continue
            if not (start <= published <= end):
                invalid_items.append({"index": index, "reason": "outside recent-news window"})

    if invalid_items:
        problems.append("one or more news items are invalid or outside the requested window")

    if not news.get("coverage_complete"):
        problems.append("host marked recent-news coverage incomplete")

    print(
        json.dumps(
            {
                "status": "ready" if not problems else "research_more",
                "problems": problems,
                "invalid_items": invalid_items,
                "valid_news_count": len(news.get("items", [])) - len(invalid_items),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
