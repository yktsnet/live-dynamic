"""Generate synthetic 5-minute bars into ``MARKET_DATA/bars/``.

Random walk with a mild trend — enough for the pipeline to produce a
signal in dry_run without touching any broker. Used by the demo and by
manual verification.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import random
from pathlib import Path


def generate_day(day: datetime.date, price: float, rng: random.Random) -> tuple[list, float]:
    rows = []
    ts = datetime.datetime.combine(day, datetime.time(0, 0), tzinfo=datetime.timezone.utc)
    end = ts + datetime.timedelta(days=1)
    trend = rng.choice([0.004, -0.004])
    while ts < end:
        drift = trend + 0.002 * math.sin(ts.hour / 3.0)
        o = price
        c = price + drift + rng.gauss(0, 0.02)
        h = max(o, c) + abs(rng.gauss(0, 0.01))
        low = min(o, c) - abs(rng.gauss(0, 0.01))
        rows.append(
            {
                "time_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": round(o, 3),
                "high": round(h, 3),
                "low": round(low, 3),
                "close": round(c, 3),
                "vol": 0,
            }
        )
        price = c
        ts += datetime.timedelta(minutes=5)
    return rows, price


def main() -> int:
    base = os.environ.get("MARKET_DATA") or os.path.expanduser("~/market_data")
    bars_dir = Path(base) / "bars"
    rng = random.Random(7)
    price = 100.0

    today = datetime.datetime.now(datetime.timezone.utc).date()
    for offset in range(4, -1, -1):
        day = today - datetime.timedelta(days=offset)
        rows, price = generate_day(day, price, rng)
        out_dir = bars_dir / day.strftime("%Y-%m")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{day.isoformat()}_m5.jsonl"
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        tmp.replace(path)
        print(f"wrote {path} ({len(rows)} bars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
