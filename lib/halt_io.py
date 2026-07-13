"""Kill-switch flag file.

Any external system (an anomaly detector, an economic-calendar watcher, or a
human with an editor) can halt trading by appending a JSONL record to
``LIVE_DYNAMIC_DATA/state/halt_flags.jsonl``:

- ``{"ts": "2026-01-05T09:00:00Z"}`` halts that whole UTC day
- ``{"start": "...", "end": "..."}`` halts the window (open-ended if ``end`` is missing)

While halted, ``build_signal`` stops emitting signals and ``halt_check``
force-closes any open position.
"""
from __future__ import annotations

import datetime
import json
from typing import Any

from lib import paths


def _parse_ts(s: Any) -> datetime.datetime | None:
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace("Z", "+00:00")
        ).astimezone(datetime.timezone.utc)
    except Exception:
        return None


def read_halt_flags() -> list[dict]:
    path = paths.get_state_dir() / "halt_flags.jsonl"
    recs: list[dict] = []
    if not path.exists():
        return recs
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    recs.append(json.loads(s))
                except Exception:
                    continue
    except Exception:
        pass
    return recs


def is_halted(ts: datetime.datetime, flags: list[dict]) -> bool:
    time_utc = ts.astimezone(datetime.timezone.utc)
    target_date = time_utc.date().isoformat()

    for rec in flags:
        start = _parse_ts(rec.get("start"))
        if start:
            end = _parse_ts(rec.get("end"))
            if end:
                if start <= time_utc <= end:
                    return True
            elif start <= time_utc:
                return True
            continue

        day_ts = _parse_ts(rec.get("ts") or rec.get("time_utc"))
        if day_ts and day_ts.date().isoformat() == target_date:
            return True

    return False
