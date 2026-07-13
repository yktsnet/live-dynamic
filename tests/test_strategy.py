import numpy as np
import pandas as pd
import pytest

from strategies.trend import strategy


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv("BT_DYNAMIC_CONFIG", "examples/config.json")
    strategy._CONFIG = None
    yield
    strategy._CONFIG = None


def _trending_bars(n=200, start=100.0, step=0.05):
    idx = pd.date_range("2026-01-05", periods=n, freq="5min", tz="UTC")
    close = start + step * np.arange(n)
    return pd.DataFrame(
        {
            "open": close - step,
            "high": close + 0.01,
            "low": close - step - 0.01,
            "close": close,
        },
        index=idx,
    )


def test_entry_on_strong_uptrend():
    df = _trending_bars()
    now = pd.Timestamp("2026-01-05T09:00:00Z")

    signal = strategy.decide(df, now)

    assert signal is not None
    assert signal["direction"] == "BUY"
    close = float(df["close"].iloc[-1])
    assert signal["tp"] == pytest.approx(close + 20 * 0.01)
    assert signal["sl"] == pytest.approx(close - 10 * 0.01)
    assert signal["ax1_class"] == "strong"


def test_no_entry_off_decision_slot():
    df = _trending_bars()
    assert strategy.decide(df, pd.Timestamp("2026-01-05T09:15:00Z")) is None


def test_no_entry_after_session_end():
    df = _trending_bars()
    assert strategy.decide(df, pd.Timestamp("2026-01-05T17:00:00Z")) is None


def test_no_entry_when_cell_unmapped(tmp_path, monkeypatch):
    # an empty regime_strategy maps every cell to None -> always flat
    import json

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"parameters": {}, "regime_strategy": {}}))
    monkeypatch.setenv("BT_DYNAMIC_CONFIG", str(config_path))
    strategy._CONFIG = None

    df = _trending_bars()
    assert strategy.decide(df, pd.Timestamp("2026-01-05T09:00:00Z")) is None
