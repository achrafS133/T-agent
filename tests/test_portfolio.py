from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.portfolio as portfolio_mod


@pytest.fixture
def portfolio_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    portfolio_file = log_dir / "portfolio.json"

    fake_config = SimpleNamespace(
        INITIAL_CASH=100_000.0,
        LOG_DIR=str(log_dir),
        MAX_POSITION_PCT=0.20,
        MIN_CASH_RESERVE_PCT=0.20,
        BROKER_FEE_PCT=0.001,
        STOP_LOSS_PCT=0.05,
    )
    monkeypatch.setattr(portfolio_mod, "config", fake_config)
    monkeypatch.setattr(portfolio_mod, "PORTFOLIO_FILE", str(portfolio_file))

    portfolio_mod.initialize_portfolio()
    return portfolio_file, fake_config


def _load(portfolio_file: Path) -> dict:
    return json.loads(portfolio_file.read_text(encoding="utf-8"))


def test_buy_success(portfolio_env):
    portfolio_file, _ = portfolio_env
    ok, msg = portfolio_mod.update_portfolio("AAPL", "BUY", 10, 150.0)
    assert ok is True
    assert msg == "Success"

    data = _load(portfolio_file)
    assert data["holdings"]["AAPL"]["qty"] == 10
    assert data["cash"] < 100_000.0
    assert len(data["snapshots"]) >= 2


def test_buy_insufficient_funds(portfolio_env):
    ok, msg = portfolio_mod.update_portfolio("AAPL", "BUY", 10_000, 150.0)
    assert ok is False
    assert "Insufficient funds" in msg or "cash reserve" in msg.lower()


def test_buy_violates_cash_reserve(portfolio_env):
    # 80% of portfolio = $80k position, leaves only $20k cash (exactly at reserve)
    ok, msg = portfolio_mod.update_portfolio("AAPL", "BUY", 500, 160.0)
    assert ok is False
    assert "cash reserve" in msg.lower()


def test_buy_exceeds_max_position(portfolio_env):
    # Max position is 20% = $20k. Buying $25k worth should fail.
    ok, msg = portfolio_mod.update_portfolio("NVDA", "BUY", 100, 250.0)
    assert ok is False
    assert "max allocation" in msg.lower()


def test_sell_success(portfolio_env):
    portfolio_file, _ = portfolio_env
    portfolio_mod.update_portfolio("AAPL", "BUY", 20, 100.0)
    cash_before = _load(portfolio_file)["cash"]

    ok, msg = portfolio_mod.update_portfolio("AAPL", "SELL", 5, 110.0)
    assert ok is True
    assert msg == "Success"

    data = _load(portfolio_file)
    assert data["holdings"]["AAPL"]["qty"] == 15
    assert data["cash"] > cash_before


def test_sell_insufficient_shares(portfolio_env):
    portfolio_mod.update_portfolio("AAPL", "BUY", 5, 100.0)
    ok, msg = portfolio_mod.update_portfolio("AAPL", "SELL", 10, 100.0)
    assert ok is False
    assert "Insufficient shares" in msg


def test_sell_removes_empty_holding(portfolio_env):
    portfolio_file, _ = portfolio_env
    portfolio_mod.update_portfolio("AAPL", "BUY", 5, 100.0)
    ok, _ = portfolio_mod.update_portfolio("AAPL", "SELL", 5, 100.0)
    assert ok is True
    assert "AAPL" not in _load(portfolio_file)["holdings"]


def test_unknown_action(portfolio_env):
    ok, msg = portfolio_mod.update_portfolio("AAPL", "HOLD", 1, 100.0)
    assert ok is False
    assert "Unknown action" in msg


def test_stop_loss_triggers(portfolio_env):
    portfolio_file, _ = portfolio_env
    portfolio_mod.update_portfolio("TSLA", "BUY", 10, 200.0)
    sells = portfolio_mod.check_stop_losses({"TSLA": 189.0})  # 5.5% drop

    assert len(sells) == 1
    assert sells[0][0] == "TSLA"
    assert "TSLA" not in _load(portfolio_file)["holdings"]


def test_stop_loss_does_not_trigger_below_threshold(portfolio_env):
    portfolio_file, _ = portfolio_env
    portfolio_mod.update_portfolio("TSLA", "BUY", 10, 200.0)
    sells = portfolio_mod.check_stop_losses({"TSLA": 196.0})  # 2% drop

    assert sells == []
    assert _load(portfolio_file)["holdings"]["TSLA"]["qty"] == 10


def test_pnl_history_includes_snapshots(portfolio_env):
    portfolio_file, fake_config = portfolio_env
    portfolio_mod.update_portfolio("MSFT", "BUY", 5, 400.0)
    history = portfolio_mod.get_pnl_history()

    assert len(history) >= 2
    assert history[-1]["total_value"] < fake_config.INITIAL_CASH


def test_broker_fee_applied_on_buy(portfolio_env):
    portfolio_file, fake_config = portfolio_env
    price = 100.0
    qty = 10
    portfolio_mod.update_portfolio("AAPL", "BUY", qty, price)

    data = _load(portfolio_file)
    expected_cost = qty * price * (1 + fake_config.BROKER_FEE_PCT)
    assert data["cash"] == pytest.approx(fake_config.INITIAL_CASH - expected_cost, rel=1e-4)
