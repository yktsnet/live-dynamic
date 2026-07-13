import pytest

from lib import oco_env


def test_round_tick():
    assert oco_env.round_tick(101.2345, 0.001) == pytest.approx(101.234)
    assert oco_env.round_tick(101.2346, 0.001) == pytest.approx(101.235)
    assert oco_env.round_tick(101.23, 0.01) == pytest.approx(101.23)


def test_choose_sides_closes_against_position():
    assert oco_env.choose_sides("Buy") == ("Sell", "Sell")
    assert oco_env.choose_sides("Sell") == ("Buy", "Buy")


def test_compute_targets_long():
    tp, sl = oco_env.compute_targets(10000, 100.0, 20, 10, 0.01, 0.001)
    assert tp == pytest.approx(100.20)
    assert sl == pytest.approx(99.90)


def test_compute_targets_short():
    tp, sl = oco_env.compute_targets(-10000, 100.0, 20, 10, 0.01, 0.001)
    assert tp == pytest.approx(99.80)
    assert sl == pytest.approx(100.10)


def test_env_precedence_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_DYNAMIC_DATA", str(tmp_path))
    env_dir = tmp_path / "env"
    env_dir.mkdir(parents=True)
    (env_dir / ".env.live_dynamic").write_text("RR_PIPS_TP=15\n", encoding="utf-8")
    oco_env._PARAMS_CACHE = None
    monkeypatch.setenv("RR_PIPS_TP", "25")
    assert oco_env.env_int("RR_PIPS_TP", 30) == 25


def test_env_falls_back_to_file_then_default(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_DYNAMIC_DATA", str(tmp_path))
    monkeypatch.delenv("RR_PIPS_TP", raising=False)
    monkeypatch.delenv("RR_PIPS_SL", raising=False)
    env_dir = tmp_path / "env"
    env_dir.mkdir(parents=True)
    (env_dir / ".env.live_dynamic").write_text("RR_PIPS_TP=15\n", encoding="utf-8")
    oco_env._PARAMS_CACHE = None
    assert oco_env.env_int("RR_PIPS_TP", 30) == 15
    assert oco_env.env_int("RR_PIPS_SL", 30) == 30
