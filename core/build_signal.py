"""Build one entry signal from the latest bars and append it to
``state/signal.jsonl``.

Signal generation and order sending are separate stages on purpose: this
script never talks to the broker, so it can run (and be tested) with no
credentials at all.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import pandas as pd

from lib import bar_loader, env_auth, halt_io, paths
from strategies.trend.strategy import DEFAULT_INDICATORS, decide, get_config


def _load_app_env() -> dict:
    path = paths.get_env_dir() / ".env.live_dynamic"
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _resolve_lot(ax1_v: float, ax1_mean: float, env: dict) -> float:
    """Inverse trend-strength sizing: the stronger the trend reading is
    versus its recent mean, the smaller the lot (TP is more likely to be
    far into an already-stretched move)."""
    base_lot = float(env.get("LOT_BASE", "0.1"))
    return base_lot * (ax1_mean / max(ax1_v, 0.1))


def _signal_path() -> Path:
    return paths.get_state_dir() / "signal.jsonl"


def _format_time_utc(ts: pd.Timestamp) -> str:
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_signal(record: dict) -> None:
    path = _signal_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")

    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(existing)
        f.write(line)

    os.replace(tmp, path)


def _is_halted(now: pd.Timestamp) -> bool:
    flags = halt_io.read_halt_flags()
    now_dt = now.to_pydatetime()
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)
    else:
        now_dt = now_dt.astimezone(datetime.timezone.utc)
    return halt_io.is_halted(now_dt, flags)


def build_signal() -> dict | None:
    env_auth.load_trade_env()  # exports BT_DYNAMIC_CONFIG etc. from the env files
    decision_minutes = get_config().params.bars_per_window * 5
    now = pd.Timestamp.utcnow().floor(f"{decision_minutes}min")
    if _is_halted(now):
        return None

    try:
        df_bars = bar_loader.load_bars()
    except ValueError as exc:
        print(f"build_signal: {exc}", file=sys.stderr)
        return None

    signal = decide(df_bars, now)
    if signal is None:
        return None

    ax1_v = float(signal["ax1_v"])
    mean_bars = get_config().params.ax2_mean_bars
    ax1_s = DEFAULT_INDICATORS.compute_ax1(df_bars)
    ax1_mean = float(ax1_s.iloc[-mean_bars:].mean())
    lot = _resolve_lot(ax1_v, ax1_mean, _load_app_env())
    record = {
        "time_utc": _format_time_utc(now),
        "direction": signal["direction"],
        "entry_price": signal["entry_price"],
        "tp": signal["tp"],
        "sl": signal["sl"],
        "lot": lot,
        "cell_mode": signal["cell_mode"],
        "ax1_v": ax1_v,
    }
    _write_signal(record)
    return record


def main() -> int:
    build_signal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
