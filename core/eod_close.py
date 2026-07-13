"""End-of-day forced close: flatten everything at the session cutoff.

Runs once per day from a systemd timer; the day key in ``state/eod.jsonl``
makes reruns idempotent.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

from lib import env_auth, force_close, paths


def _eod_path() -> Path:
    return paths.get_state_dir() / "eod.jsonl"


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _format_time_utc(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    else:
        ts = ts.astimezone(datetime.timezone.utc)
    return ts.isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_done(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("key") == key:
                return True
        except Exception:
            continue
    return False


def _append_record(path: Path, record: dict) -> None:
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


def _close_all() -> bool:
    try:
        force_close.close_all_positions()
        return True
    except Exception as e:
        reason = str(e).split()[0] if str(e).strip() else "error"
        if reason in ("NoPos", "NoAmt"):
            return True
        return False


def run_eod_close(now: datetime.datetime | None = None) -> bool | None:
    env_auth.load_trade_env()
    now = now or _now_utc()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    else:
        now = now.astimezone(datetime.timezone.utc)

    key = f"eod_close_{now.date().isoformat()}"
    path = _eod_path()
    if _is_done(path, key):
        return None

    ok = _close_all()
    record = {
        "key": key,
        "ts": _format_time_utc(now),
        "date": now.date().isoformat(),
        "extra": {"ok": ok},
    }
    _append_record(path, record)
    return ok


def main() -> int:
    ok = run_eod_close()
    return 1 if ok is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
