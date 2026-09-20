"""Compute deterministic short-term market features from daily K-line data."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def numbers(rows: list[dict], field: str) -> list[float]:
    return [float(row[field]) for row in rows if row.get(field) is not None]


def avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return round((new / old - 1.0) * 100.0, 4)


def moving_average(closes: list[float], size: int) -> float | None:
    if len(closes) < size:
        return None
    return round(sum(closes[-size:]) / size, 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    market = json.loads(Path(args.market).read_text(encoding="utf-8"))
    rows = market["rows"]
    if len(rows) < 2:
        raise RuntimeError("at least two market rows are required")

    closes = numbers(rows, "close")
    volumes = numbers(rows, "volume")
    turnovers = numbers(rows, "turnover_rate_pct")
    amplitudes = numbers(rows, "amplitude_pct")
    daily_changes = numbers(rows, "change_pct")

    latest = rows[-1]
    first = rows[0]

    recent5_volumes = volumes[-5:]
    previous5_volumes = volumes[-10:-5] if len(volumes) >= 10 else []
    recent5_turnover = turnovers[-5:]
    previous5_turnover = turnovers[-10:-5] if len(turnovers) >= 10 else []

    volume_baseline = avg(volumes[:-1]) if len(volumes) > 1 else None
    turnover_baseline = avg(turnovers[:-1]) if len(turnovers) > 1 else None

    anomalies = []
    for row in rows:
        reasons = []
        if volume_baseline and row.get("volume") is not None and float(row["volume"]) >= volume_baseline * 1.8:
            reasons.append("volume>=1.8x_period_baseline")
        if turnover_baseline and row.get("turnover_rate_pct") is not None and float(row["turnover_rate_pct"]) >= turnover_baseline * 1.5:
            reasons.append("turnover>=1.5x_period_baseline")
        if row.get("change_pct") is not None and abs(float(row["change_pct"])) >= 7:
            reasons.append("abs_daily_change>=7pct")
        if reasons:
            anomalies.append({"date": row["date"], "reasons": reasons})

    ma5 = moving_average(closes, 5)
    ma10 = moving_average(closes, 10)
    ma20 = moving_average(closes, 20)

    features = {
        "sample": {
            "trading_days": len(rows),
            "first_date": first["date"],
            "last_date": latest["date"],
        },
        "price": {
            "latest_close": latest.get("close"),
            "period_return_pct": pct_change(float(latest["close"]), float(first["close"])),
            "period_high": max(numbers(rows, "high")),
            "period_low": min(numbers(rows, "low")),
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "latest_vs_ma5_pct": pct_change(float(latest["close"]), ma5) if ma5 else None,
            "latest_vs_ma10_pct": pct_change(float(latest["close"]), ma10) if ma10 else None,
        },
        "volume": {
            "latest": latest.get("volume"),
            "period_average": avg(volumes),
            "recent5_average": avg(recent5_volumes),
            "previous5_average": avg(previous5_volumes),
            "recent5_vs_previous5_pct": (
                pct_change(avg(recent5_volumes), avg(previous5_volumes))
                if previous5_volumes
                else None
            ),
        },
        "turnover": {
            "latest_pct": latest.get("turnover_rate_pct"),
            "period_average_pct": avg(turnovers),
            "recent5_average_pct": avg(recent5_turnover),
            "previous5_average_pct": avg(previous5_turnover),
            "recent5_vs_previous5_pct": (
                pct_change(avg(recent5_turnover), avg(previous5_turnover))
                if previous5_turnover
                else None
            ),
            "period_max_pct": max(turnovers) if turnovers else None,
        },
        "volatility": {
            "average_amplitude_pct": avg(amplitudes),
            "daily_change_std_pct": (
                round(statistics.pstdev(daily_changes), 4)
                if len(daily_changes) >= 2
                else None
            ),
        },
        "anomalies": anomalies,
    }

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(features, ensure_ascii=False))


if __name__ == "__main__":
    main()
