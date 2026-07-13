"""Send the latest signal to the broker, exactly once per decision slot.

Safety layers, in order: the ``time_utc`` dedupe against ``sent.jsonl``
(idempotency), the ``ENABLE_EXEC_REQUESTS`` gate (dry_run by default), and
the OCO bracket placed right after a filled entry.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from lib import broker_client, env_auth, oco_manager, paths, token_io


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


def _signal_path() -> Path:
    return paths.get_state_dir() / "signal.jsonl"


def _sent_path() -> Path:
    return paths.get_state_dir() / "sent.jsonl"


def _read_last_signal(path: Path) -> dict | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except Exception:
                return None
    return None


def _already_sent(sent_path: Path, time_utc: str) -> bool:
    if not sent_path.exists():
        return False
    for line in sent_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("time_utc") == time_utc:
                return True
        except Exception:
            continue
    return False


def _append_sent(sent_path: Path, record: dict) -> None:
    sent_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"

    existing = ""
    if sent_path.exists():
        existing = sent_path.read_text(encoding="utf-8")

    tmp = str(sent_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(existing)
        f.write(line)

    os.replace(tmp, sent_path)


def _calc_net_lot(sent_path: Path, new_direction: str, new_lot: float) -> float:
    net = 0.0
    if sent_path.exists():
        for line in sent_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("status") != "ok" or rec.get("dry_run"):
                    continue
                direction = 1 if rec.get("direction") == "BUY" else -1
                net += direction * float(rec.get("lot", 0))
            except Exception:
                continue

    new_direction_sign = 1 if new_direction == "BUY" else -1
    return net + new_direction_sign * new_lot


def _place_order(signal: dict, dry_run: bool, account_key: str | None) -> tuple[bool, int]:
    if dry_run:
        return True, 0

    try:
        token = token_io.get_access_token()
        status_code, _resp = broker_client.place_market_order(
            token,
            signal["lot"],
            signal["direction"],
            account_key,
            manual_order=False,
        )
    except Exception as exc:
        print(f"sender_gate: place_market_order error: {exc}", file=sys.stderr)
        return False, 0

    return status_code in (200, 201), status_code


def send_latest_signal() -> dict | None:
    signal = _read_last_signal(_signal_path())
    if not signal:
        return None

    time_utc = signal.get("time_utc")
    if not time_utc:
        return None

    sent_path = _sent_path()
    if _already_sent(sent_path, time_utc):
        return None

    trade_cfg = env_auth.load_trade_env()
    account_key = trade_cfg.get("ACCOUNT_KEY")
    app_cfg = _load_app_env()
    dry_run = int(app_cfg.get("ENABLE_EXEC_REQUESTS", "0")) != 1
    success, status_code = _place_order(signal, dry_run, account_key)

    sent_record = {
        "time_utc": signal["time_utc"],
        "status": "ok" if success else "fail",
        "status_code": status_code,
        "dry_run": dry_run,
        "direction": signal["direction"],
        "lot": signal["lot"],
        "net_lot": _calc_net_lot(sent_path, signal["direction"], signal["lot"])
        if success and not dry_run
        else None,
    }
    _append_sent(sent_path, sent_record)

    if not success:
        return sent_record

    if not dry_run:
        try:
            res = oco_manager.ensure()
            print(f"sender_gate: oco_ensure result={res}")
        except Exception as exc:
            print(f"sender_gate: oco_ensure error: {exc}")

    return sent_record


def main() -> int:
    send_latest_signal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
