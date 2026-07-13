"""Parameter loading from ``LIVE_DYNAMIC_DATA/env/`` files.

Load order: ``.env.trade.base`` then ``.env.live_dynamic``; process env
vars override file values.
"""
from __future__ import annotations

import os
from pathlib import Path

from lib import paths


def _load_file(p: Path, d: dict) -> dict:
    if not p.exists():
        return d
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def load_params() -> dict:
    env_dir = paths.get_env_dir()

    params: dict = {}
    _load_file(env_dir / ".env.trade.base", params)
    _load_file(env_dir / ".env.live_dynamic", params)

    for k in list(params.keys()):
        env_val = os.environ.get(k)
        if env_val is not None:
            params[k] = env_val

    return params
