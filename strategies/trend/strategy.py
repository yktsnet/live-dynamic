"""Live decision layer on top of the ``bt-dynamic`` package.

Everything strategy-specific (the cell mapping, thresholds, TP/SL) comes
from the same config JSON the backtest uses, loaded via
``$BT_DYNAMIC_CONFIG``. Nothing in this repo carries production values.
"""
from __future__ import annotations

import pandas as pd
from bt_dynamic.config import Config
from bt_dynamic.engine import resolve_entry
from bt_dynamic.indicators import DEFAULT_INDICATORS
from bt_dynamic.regime import classify

_CONFIG: Config | None = None

BAR_MINUTES = 5


def get_config() -> Config:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = Config.load()
    return _CONFIG


def _ax1_class_label(ax1_v: float, params) -> str:
    if ax1_v < params.ax1_weak:
        return "weak"
    if ax1_v < params.ax1_strong:
        return "mid"
    return "strong"


def decide(df_bars: pd.DataFrame, now: pd.Timestamp) -> dict | None:
    config = get_config()
    params = config.params

    decision_minutes = params.bars_per_window * BAR_MINUTES
    if now.minute % decision_minutes != 0:
        return None
    if now.hour >= params.trade_end_hour:
        return None

    ind = DEFAULT_INDICATORS
    ax1_s = ind.compute_ax1(df_bars)
    ax2_s = ind.compute_ax2(df_bars)
    ax2_mean_s = ind.compute_ax2_mean(ax2_s, params.ax2_mean_bars)
    dir_s = ind.compute_direction(df_bars)

    ax1_v = float(ax1_s.iloc[-1])
    ax2_v = float(ax2_s.iloc[-1])
    ax2_mean_v = float(ax2_mean_s.iloc[-1])
    dir_v = float(dir_s.iloc[-1])

    if any(pd.isna(v) for v in [ax1_v, ax2_v, ax2_mean_v, dir_v]):
        return None

    ax1_class, ax2_class, direction = classify(
        ax1_v,
        ax2_v,
        ax2_mean_v,
        dir_v,
        ax1_weak=params.ax1_weak,
        ax1_strong=params.ax1_strong,
        vol_lo=params.vol_lo,
        vol_hi=params.vol_hi,
        direction_band=params.direction_band,
        direction_center=params.direction_center,
    )
    cell_mode = config.regime_strategy.get((ax1_class, ax2_class))

    close_price = float(df_bars["close"].iloc[-1])
    entry = resolve_entry(close_price, cell_mode, direction, params)
    if entry is None:
        return None

    return {**entry, "ax1_v": ax1_v, "ax1_class": _ax1_class_label(ax1_v, params)}
