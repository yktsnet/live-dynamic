"""Kill-switch check: while a halt flag is active, force-close everything.

Runs every 5 minutes. Each 5-minute slot is recorded in
``state/halt_log.jsonl`` so a rerun inside the same slot is a no-op.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

from lib import env_auth, force_close, halt_io, paths


def _log_path() -> Path:
    return paths.get_state_dir() / "halt_log.jsonl"


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _format_time_utc(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    else:
        ts = ts.astimezone(datetime.timezone.utc)
    return ts.isoformat(timespec="seconds").replace("+00:00", "Z")


def _slot_key(now: datetime.datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    else:
        now = now.astimezone(datetime.timezone.utc)
    slot = now.replace(second=0, microsecond=0)
    slot = slot.replace(minute=(slot.minute // 5) * 5)
    return f"halt_check_{slot.strftime('%Y%m%dT%H%M')}Z"


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


def run_halt_check(now: datetime.datetime | None = None) -> bool | None:
    env_auth.load_trade_env()
    now = now or _now_utc()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    else:
        now = now.astimezone(datetime.timezone.utc)

    flags = halt_io.read_halt_flags()
    if not halt_io.is_halted(now, flags):
        return None

    key = _slot_key(now)
    path = _log_path()
    if _is_done(path, key):
        return True

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
    ok = run_halt_check()
    return 1 if ok is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
