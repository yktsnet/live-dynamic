"""Token file I/O.

The token lives at ``MARKET_DATA/state/tokens/live_current.json`` so the
fetch side and the trade side share one refresh cycle. Override with
``BROKER_TOKEN_FILE``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from lib import paths


def get_token_file_path() -> Path:
    env_path = os.environ.get("BROKER_TOKEN_FILE") or os.environ.get("TOKEN_FILE")
    if env_path:
        return Path(env_path)
    d = paths.get_tokens_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "live_current.json"


def load_token() -> dict:
    p = get_token_file_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_token(token_data: dict) -> None:
    p = get_token_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)


def get_access_token() -> str:
    data = load_token()
    return data.get("access_token")
