"""Resolve the stock target and deterministic analysis windows."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def exchange_for(symbol: str) -> str:
    if symbol.startswith("68"):
        return "SSE STAR Market"
    if symbol.startswith(("60", "601", "603", "605")):
        return "SSE"
    if symbol.startswith(("00", "30")):
        return "SZSE"
    if symbol.startswith(("4", "8", "9")):
        return "BSE"
    return "A-share"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--news-days", type=int, default=3)
    parser.add_argument("--market-days", type=int, default=20)
    args = parser.parse_args()

    if not (args.symbol.isdigit() and len(args.symbol) == 6):
        raise SystemExit("--symbol must be a six-digit A-share code")
    if args.news_days < 1:
        raise SystemExit("--news-days must be >= 1")
    if args.market_days < 5:
        raise SystemExit("--market-days must be >= 5")

    as_of = parse_date(args.as_of)
    news_start = as_of - timedelta(days=args.news_days - 1)

    # Pull a wider calendar range and let fetch_market_data.py keep the most
    # recent N trading rows. This avoids embedding a trading-calendar service.
    market_start = as_of - timedelta(days=max(45, args.market_days * 3))

    print(
        json.dumps(
            {
                "name": args.name,
                "symbol": args.symbol,
                "exchange": exchange_for(args.symbol),
                "as_of": as_of.isoformat(),
                "news_start": news_start.isoformat(),
                "news_end": as_of.isoformat(),
                "news_days": args.news_days,
                "market_days": args.market_days,
                "market_fetch_start": market_start.isoformat(),
                "market_fetch_end": as_of.isoformat(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
