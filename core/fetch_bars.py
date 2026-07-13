"""Fetch 5-minute OHLC bars from the broker chart API into
``MARKET_DATA/bars/YYYY-MM/YYYY-MM-DD_m5.jsonl`` (one file per UTC day,
written atomically).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path

from lib.chart_client import ChartClient
from lib import paths

UTC = datetime.timezone.utc


def _fetch_range_bars(client: ChartClient, instrument_id: int, start_dt: datetime.datetime) -> list:
    s_dt = start_dt.replace(microsecond=0)
    s_str = s_dt.isoformat().replace("+00:00", "Z")
    print(f"Fetching {s_str}")
    try:
        data = client.get_chart_data(instrument_id, s_str, None, horizon=5)
    except Exception as e:
        print(f"[WARN] Failed request for {s_str}: {e}")
        return []

    if not data:
        return []

    rows = []
    for d in data:
        ts = d.get("Time")
        if not ts:
            continue
        rows.append(
            {
                "time_utc": ts,
                "open": d.get("OpenBid"),
                "high": d.get("HighBid"),
                "low": d.get("LowBid"),
                "close": d.get("CloseBid"),
                "vol": d.get("Volume", 0),
            }
        )
    return rows


def _write_by_day(bars_dir: Path, rows: list) -> None:
    bars_dir.mkdir(parents=True, exist_ok=True)
    buckets: dict = {}

    for r in rows:
        ts = r["time_utc"]
        if not ts or len(ts) < 10:
            continue
        buckets.setdefault(ts[:10], []).append(r)

    for day_str, items in buckets.items():
        out_dir = bars_dir / day_str[:7]
        out_dir.mkdir(parents=True, exist_ok=True)

        path = out_dir / f"{day_str}_m5.jsonl"
        tmp_path = path.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, separators=(",", ":")) + "\n")

        tmp_path.replace(path)


def run(mode: str = "today", years: int = 5) -> None:
    instrument_id = os.environ.get("INSTRUMENT_ID")
    if not instrument_id:
        print("[error] missing INSTRUMENT_ID in env")
        return
    instrument_id = int(instrument_id)

    try:
        client = ChartClient()
    except Exception as e:
        print(f"Failed to initialize ChartClient: {e}")
        return

    now = datetime.datetime.now(UTC)

    if mode == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
    elif mode == "month":
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        print("Running MONTH mode")
    elif mode == "backfill":
        start_dt = now - datetime.timedelta(days=365 * years)
        end_dt = now
        print(f"Running BACKFILL mode: {years} years")
    else:
        try:
            start_dt = datetime.datetime.strptime(mode, "%Y-%m").replace(tzinfo=UTC)
            if start_dt.month == 12:
                next_month = start_dt.replace(year=start_dt.year + 1, month=1)
            else:
                next_month = start_dt.replace(month=start_dt.month + 1)
            end_dt = min(next_month, now)
            print(f"Running SPECIFIED MONTH mode: {mode}")
        except ValueError:
            print(f"Unknown mode or invalid date format: {mode}")
            return

    bars_dir = paths.get_bars_dir()
    current_start = start_dt
    while current_start < end_dt:
        chunk_end = min(current_start + datetime.timedelta(days=1), end_dt)
        rows = _fetch_range_bars(client, instrument_id, current_start)
        if rows:
            _write_by_day(bars_dir, rows)
        current_start = chunk_end


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch 5m bars into MARKET_DATA/bars/")
    parser.add_argument("mode", nargs="?", default="today", help="today, month, backfill, or YYYY-MM")
    parser.add_argument("--years", type=int, default=5, help="Years to backfill")
    args = parser.parse_args()
    run(args.mode, args.years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
