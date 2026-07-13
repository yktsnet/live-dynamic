"""OCO parameter access (env vars first, env files as fallback) and
pure price helpers for bracket targets."""
from __future__ import annotations

import os

from lib.env_loader import load_params

_PARAMS_CACHE = None


def _get_params():
    global _PARAMS_CACHE
    if _PARAMS_CACHE is None:
        _PARAMS_CACHE = load_params()
    return _PARAMS_CACHE


def env_str(k, d):
    v = os.environ.get(k)
    if v not in (None, ""):
        return v
    p = _get_params()
    v = p.get(k)
    return v if v not in (None, "") else d


def env_int(k, d):
    try:
        return int(env_str(k, str(d)))
    except Exception:
        return int(d)


def env_float(k, d):
    try:
        return float(env_str(k, str(d)))
    except Exception:
        return float(d)


def round_tick(x, tick):
    return round(round(x / tick) * tick, 10)


def choose_sides(net_dir):
    return ("Sell", "Sell") if net_dir == "Buy" else ("Buy", "Buy")


def compute_targets(net, avg, tp_pips, sl_pips, pip, tick):
    if net > 0:
        tp = avg + tp_pips * pip
        sl = avg - sl_pips * pip
    else:
        tp = avg - tp_pips * pip
        sl = avg + sl_pips * pip
    return round_tick(tp, tick), round_tick(sl, tick)
