import json

from core import sender_gate


def _setup_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_DYNAMIC_DATA", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "env").mkdir(parents=True, exist_ok=True)


def _write_signal(tmp_path, record):
    path = tmp_path / "state" / "signal.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


SIGNAL = {
    "time_utc": "2026-01-05T09:00:00Z",
    "direction": "BUY",
    "entry_price": 100.0,
    "tp": 100.2,
    "sl": 99.9,
    "lot": 0.1,
}


def test_dry_run_records_without_broker(tmp_path, monkeypatch):
    _setup_dirs(tmp_path, monkeypatch)
    _write_signal(tmp_path, SIGNAL)

    rec = sender_gate.send_latest_signal()

    assert rec["status"] == "ok"
    assert rec["dry_run"] is True
    assert rec["net_lot"] is None
    sent_lines = (tmp_path / "state" / "sent.jsonl").read_text().splitlines()
    assert len(sent_lines) == 1


def test_same_slot_is_sent_only_once(tmp_path, monkeypatch):
    _setup_dirs(tmp_path, monkeypatch)
    _write_signal(tmp_path, SIGNAL)

    assert sender_gate.send_latest_signal() is not None
    assert sender_gate.send_latest_signal() is None
    sent_lines = (tmp_path / "state" / "sent.jsonl").read_text().splitlines()
    assert len(sent_lines) == 1


def test_new_slot_is_sent_again(tmp_path, monkeypatch):
    _setup_dirs(tmp_path, monkeypatch)
    _write_signal(tmp_path, SIGNAL)
    assert sender_gate.send_latest_signal() is not None

    _write_signal(tmp_path, {**SIGNAL, "time_utc": "2026-01-05T09:30:00Z"})
    assert sender_gate.send_latest_signal() is not None
    sent_lines = (tmp_path / "state" / "sent.jsonl").read_text().splitlines()
    assert len(sent_lines) == 2


def test_no_signal_is_a_noop(tmp_path, monkeypatch):
    _setup_dirs(tmp_path, monkeypatch)
    assert sender_gate.send_latest_signal() is None
    assert not (tmp_path / "state" / "sent.jsonl").exists()


def test_calc_net_lot_ignores_dry_run_and_failures(tmp_path, monkeypatch):
    _setup_dirs(tmp_path, monkeypatch)
    sent = tmp_path / "state" / "sent.jsonl"
    rows = [
        {"status": "ok", "dry_run": False, "direction": "BUY", "lot": 0.2},
        {"status": "ok", "dry_run": True, "direction": "BUY", "lot": 9.9},
        {"status": "fail", "dry_run": False, "direction": "BUY", "lot": 9.9},
        {"status": "ok", "dry_run": False, "direction": "SELL", "lot": 0.05},
    ]
    sent.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    net = sender_gate._calc_net_lot(sent, "BUY", 0.1)
    assert abs(net - 0.25) < 1e-9
