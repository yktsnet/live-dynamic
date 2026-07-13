"""Path resolution. All state lives under two roots:

- ``LIVE_DYNAMIC_DATA``: this app's state / logs / env files
- ``MARKET_DATA``: bar data and tokens, shared with the fetch side
"""
from __future__ import annotations

import os
from pathlib import Path


def _env_path(key: str, default_home_rel: str) -> Path:
    val = os.environ.get(key)
    if val:
        return Path(val).expanduser()
    return Path.home() / default_home_rel


def get_data_root() -> Path:
    return _env_path("LIVE_DYNAMIC_DATA", "live_dynamic_data")


def get_state_dir() -> Path:
    return get_data_root() / "state"


def get_log_dir() -> Path:
    return get_data_root() / "logs"


def get_env_dir() -> Path:
    return get_data_root() / "env"


def get_market_data_root() -> Path:
    return _env_path("MARKET_DATA", "market_data")


def get_bars_dir() -> Path:
    return get_market_data_root() / "bars"


def get_tokens_dir() -> Path:
    return get_market_data_root() / "state" / "tokens"
