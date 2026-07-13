import datetime
import json

from lib import halt_io

UTC = datetime.timezone.utc


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_not_halted_without_flags():
    assert halt_io.is_halted(ts("2026-01-05T09:00:00Z"), []) is False


def test_day_flag_halts_that_utc_day_only():
    flags = [{"ts": "2026-01-05T03:00:00Z"}]
    assert halt_io.is_halted(ts("2026-01-05T09:00:00Z"), flags) is True
    assert halt_io.is_halted(ts("2026-01-05T23:59:59Z"), flags) is True
    assert halt_io.is_halted(ts("2026-01-06T00:00:00Z"), flags) is False


def test_window_flag_halts_inside_window():
    flags = [{"start": "2026-01-05T12:00:00Z", "end": "2026-01-05T14:00:00Z"}]
    assert halt_io.is_halted(ts("2026-01-05T11:59:59Z"), flags) is False
    assert halt_io.is_halted(ts("2026-01-05T12:00:00Z"), flags) is True
    assert halt_io.is_halted(ts("2026-01-05T14:00:00Z"), flags) is True
    assert halt_io.is_halted(ts("2026-01-05T14:00:01Z"), flags) is False


def test_open_ended_window_halts_forever_after_start():
    flags = [{"start": "2026-01-05T12:00:00Z"}]
    assert halt_io.is_halted(ts("2026-01-05T11:00:00Z"), flags) is False
    assert halt_io.is_halted(ts("2027-06-01T00:00:00Z"), flags) is True


def test_malformed_records_are_ignored():
    flags = [{"ts": "not-a-date"}, {"start": None}, {}]
    assert halt_io.is_halted(ts("2026-01-05T09:00:00Z"), flags) is False


def test_read_halt_flags_skips_broken_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_DYNAMIC_DATA", str(tmp_path))
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "halt_flags.jsonl").write_text(
        json.dumps({"ts": "2026-01-05T03:00:00Z"}) + "\nnot json\n\n",
        encoding="utf-8",
    )
    flags = halt_io.read_halt_flags()
    assert flags == [{"ts": "2026-01-05T03:00:00Z"}]


def test_read_halt_flags_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_DYNAMIC_DATA", str(tmp_path))
    assert halt_io.read_halt_flags() == []
