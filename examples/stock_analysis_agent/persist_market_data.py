"""Validate and persist real market rows collected by the host fallback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_NUMERIC = ("open", "close", "high", "low", "volume", "turnover_rate_pct")


def as_number(value, field: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"row {index} field {field} must be numeric")
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--research-json", required=True)
    parser.add_argument("--market-days", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    research = json.loads(args.research_json)
    rows = research.get("rows", [])
    source_urls = research.get("source_urls", [])

    problems = []
    if research.get("coverage_complete") is not True:
        problems.append("host market research is not marked coverage_complete")
    if len(source_urls) < 1 or not all(isinstance(url, str) and url.startswith(("http://", "https://")) for url in source_urls):
        problems.append("host market research must include at least one source URL")
    if len(rows) < 5:
        problems.append("host market research must contain at least 5 real trading rows")

    if problems:
        print(json.dumps({"status": "invalid", "problems": problems}, ensure_ascii=False))
        return

    rows = sorted(rows, key=lambda row: row.get("date", ""))
    normalized = []
    previous_close = None
    for index, row in enumerate(rows):
        if not isinstance(row.get("date"), str):
            print(json.dumps({"status": "invalid", "problems": [f"row {index} is missing date"]}, ensure_ascii=False))
            return
        item = {"date": row["date"]}
        try:
            for field in REQUIRED_NUMERIC:
                item[field] = as_number(row.get(field), field, index)
        except RuntimeError as exc:
            print(json.dumps({"status": "invalid", "problems": [str(exc)]}, ensure_ascii=False))
            return

        turnover_value = row.get("turnover_value")
        try:
            item["turnover_value"] = (
                None if turnover_value is None else as_number(turnover_value, "turnover_value", index)
            )
        except RuntimeError as exc:
            print(json.dumps({"status": "invalid", "problems": [str(exc)]}, ensure_ascii=False))
            return

        item["amplitude_pct"] = round(
            (item["high"] - item["low"]) / item["close"] * 100.0, 4
        ) if item["close"] else None

        if previous_close:
            item["change_value"] = round(item["close"] - previous_close, 4)
            item["change_pct"] = round((item["close"] / previous_close - 1.0) * 100.0, 4)
        else:
            item["change_value"] = None
            item["change_pct"] = None

        previous_close = item["close"]
        normalized.append(item)

    normalized.sort(key=lambda row: row["date"])
    normalized = normalized[-args.market_days :]

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": args.symbol,
        "source": "host-web-research",
        "source_urls": source_urls,
        "source_note": research.get("source_note", ""),
        "adjust": "",
        "rows": normalized,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = normalized[-1]
    print(json.dumps({
        "status": "ready",
        "market_file": str(output),
        "source": "host-web-research",
        "source_urls": source_urls,
        "row_count": len(normalized),
        "first_date": normalized[0]["date"],
        "last_date": latest["date"],
        "latest": latest,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
