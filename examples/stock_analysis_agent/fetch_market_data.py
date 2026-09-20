"""Try AKShare first; return a host-fallback request instead of inventing market data."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any


COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "turnover_value",
    "振幅": "amplitude_pct",
    "涨跌幅": "change_pct",
    "涨跌额": "change_value",
    "换手率": "turnover_rate_pct",
}


def json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in records:
        item = {}
        for source, target in COLUMN_MAP.items():
            if source in row:
                item[target] = json_value(row[source])
        if "date" not in item:
            raise RuntimeError("AKShare result is missing 日期")
        normalized.append(item)
    normalized.sort(key=lambda item: item["date"])
    return normalized


def load_fixture(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("rows")
    if not isinstance(value, list):
        raise RuntimeError("fixture must be a JSON list or an object containing rows")
    return value


def ready_payload(*, symbol: str, rows: list[dict[str, Any]], source: str, output: Path) -> dict:
    rows = rows
    if not rows:
        raise RuntimeError("market-data result is empty")

    payload = {
        "symbol": symbol,
        "source": source,
        "source_urls": [],
        "adjust": "",
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = rows[-1]
    return {
        "status": "ready",
        "market_file": str(output),
        "source": source,
        "row_count": len(rows),
        "first_date": rows[0]["date"],
        "last_date": latest["date"],
        "latest": latest,
    }


def fallback_payload(*, symbol: str, start: str, end: str, market_days: int, error: BaseException) -> dict:
    return {
        "status": "needs_host_fallback",
        "symbol": symbol,
        "requested_start": start,
        "requested_end": end,
        "market_days": market_days,
        "reason": f"{type(error).__name__}: {error}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--market-days", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--force-fallback", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output = Path(args.output).resolve()

    if args.fixture:
        rows = load_fixture(Path(args.fixture))[-args.market_days :]
        result = ready_payload(
            symbol=args.symbol,
            rows=rows,
            source="fixture-ci-only",
            output=output,
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    try:
        if args.force_fallback:
            raise ConnectionError("forced host market-data fallback for test")

        import akshare as ak

        frame = ak.stock_zh_a_hist(
            symbol=args.symbol,
            period="daily",
            start_date=args.start.replace("-", ""),
            end_date=args.end.replace("-", ""),
            adjust="",
        )
        if frame is None or frame.empty:
            raise RuntimeError(f"AKShare returned no daily data for {args.symbol}")

        rows = normalize_records(frame.to_dict(orient="records"))[-args.market_days :]
        result = ready_payload(
            symbol=args.symbol,
            rows=rows,
            source="AKShare.stock_zh_a_hist",
            output=output,
        )
    except Exception as exc:
        # Network/package/provider failure is a recoverable workflow condition.
        # Do not synthesize prices here. The Workflow will yield a host-native
        # web-research task that must return sourced real market data.
        result = fallback_payload(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            market_days=args.market_days,
            error=exc,
        )

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
