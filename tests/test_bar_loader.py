import datetime
import json

import pytest

from lib import bar_loader


def _write_day(bars_dir, day, closes):
    out_dir = bars_dir / day.strftime("%Y-%m")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}_m5.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(closes):
            ts = datetime.datetime.combine(
                day, datetime.time(0, 0), tzinfo=datetime.timezone.utc
            ) + datetime.timedelta(minutes=5 * i)
            f.write(
                json.dumps(
                    {
                        "time_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "open": c,
                        "high": c,
                        "low": c,
                        "close": c,
                    }
                )
                + "\n"
            )


def test_loads_today_plus_warmup_sorted(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA", str(tmp_path))
    bars_dir = tmp_path / "bars"
    today = datetime.date.today()
    _write_day(bars_dir, today, [3.0, 4.0])
    _write_day(bars_dir, today - datetime.timedelta(days=1), [2.0])
    _write_day(bars_dir, today - datetime.timedelta(days=2), [1.0])

    df = bar_loader.load_bars(warmup_days=2)

    assert list(df["close"]) == [1.0, 2.0, 3.0, 4.0]
    assert list(df.columns) == ["open", "high", "low", "close"]


def test_skips_missing_days(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA", str(tmp_path))
    bars_dir = tmp_path / "bars"
    today = datetime.date.today()
    _write_day(bars_dir, today, [2.0])
    _write_day(bars_dir, today - datetime.timedelta(days=3), [1.0])

    df = bar_loader.load_bars(warmup_days=1)
    assert list(df["close"]) == [1.0, 2.0]


def test_raises_when_no_data(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA", str(tmp_path))
    with pytest.raises(ValueError):
        bar_loader.load_bars()
