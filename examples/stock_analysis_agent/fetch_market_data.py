"""Fetch recent A-share daily market data with AKShare."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--market-days", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.fixture:
        rows = load_fixture(Path(args.fixture))
        source = "fixture"
    else:
        try:
            import akshare as ak
        except ImportError as exc:
            raise SystemExit(
                "AKShare is required for live market data. "
                "Run: pip install -r examples/stock_analysis_agent/requirements.txt"
            ) from exc

        frame = ak.stock_zh_a_hist(
            symbol=args.symbol,
            period="daily",
            start_date=args.start.replace("-", ""),
            end_date=args.end.replace("-", ""),
            adjust="",
        )
        if frame is None or frame.empty:
            raise RuntimeError(f"AKShare returned no daily data for {args.symbol}")
        rows = normalize_records(frame.to_dict(orient="records"))
        source = "AKShare.stock_zh_a_hist"

    rows = rows[-args.market_days :]
    if not rows:
        raise RuntimeError("market-data result is empty")

    payload = {
        "symbol": args.symbol,
        "source": source,
        "adjust": "",
        "rows": rows,
    }

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = rows[-1]
    print(
        json.dumps(
            {
                "market_file": str(output),
                "source": source,
                "row_count": len(rows),
                "first_date": rows[0]["date"],
                "last_date": latest["date"],
                "latest": latest,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
