"""Credential and trade-parameter loading.

Secrets live outside the repo in ``LIVE_DYNAMIC_DATA/env/``. Load order:
``.env.trade.base`` then ``.env.live_dynamic``; already-set process env
vars win over file values.
"""
from __future__ import annotations

import os

from lib import paths


def _load_env_file(path, d):
    if not path.exists():
        return d
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


TARGET_KEYS = [
    "ACCOUNT_KEY",
    "CLIENT_KEY",
    "BROKER_CLIENT_ID",
    "BROKER_AUTH_BASE",
    "BROKER_REDIRECT_URI",
    "BROKER_API_BASE",
    "ENABLE_EXEC_REQUESTS",
    "BROKER_SYMBOL",
    "INSTRUMENT_ID",
    "ASSET_TYPE",
    "PIP_SIZE",
    "TICK_SIZE",
    "RR_PIPS_TP",
    "RR_PIPS_SL",
    "LOT_SIZE",
    "LOT_BASE",
    "BT_DYNAMIC_CONFIG",
]


def load_trade_env() -> dict:
    env_dir = paths.get_env_dir()

    cfg: dict = {}
    _load_env_file(env_dir / ".env.trade.base", cfg)
    _load_env_file(env_dir / ".env.live_dynamic", cfg)

    for k, v in cfg.items():
        if os.environ.get(k) is None:
            os.environ[k] = str(v)

    for k in TARGET_KEYS:
        if os.environ.get(k) is not None:
            cfg[k] = os.environ.get(k)

    return cfg


def get_broker_config() -> dict:
    cfg = load_trade_env()
    return {
        "account_key": cfg.get("ACCOUNT_KEY"),
        "client_key": cfg.get("CLIENT_KEY"),
        "client_id": cfg.get("BROKER_CLIENT_ID"),
        "auth_base": cfg.get("BROKER_AUTH_BASE"),
        "redirect_uri": cfg.get("BROKER_REDIRECT_URI"),
    }
