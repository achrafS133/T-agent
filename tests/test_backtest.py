from __future__ import annotations

from unittest.mock import patch

import pytest

from src.backtest import load_backtest_results, process_backtest_row, summarize_backtest


def test_process_backtest_row_skips_header():
    assert process_backtest_row("| Date | Ticker | Action |") is None
    assert process_backtest_row("|------|--------|--------|") is None


def test_process_backtest_row_hold_zero_roi():
    line = "| 2024-01-15 | AAPL | HOLD | 0 | some reason |"
    with patch("src.backtest.yf") as mock_yf:
        mock_yf.Ticker.return_value.history.return_value = _fake_hist(100.0, 110.0)
        result = process_backtest_row(line)

    assert result is not None
    assert result["action"] == "HOLD"
    assert result["roi"] == 0.0


def test_process_backtest_row_buy_positive_roi():
    line = "| 2024-01-15 | AAPL | BUY | 5 | bullish |"
    with patch("src.backtest.yf") as mock_yf:
        mock_yf.Ticker.return_value.history.return_value = _fake_hist(100.0, 115.0)
        result = process_backtest_row(line)

    assert result["roi"] == pytest.approx(15.0)
    assert result["ticker"] == "AAPL"


def test_process_backtest_row_sell_inverts_roi():
    line = "| 2024-01-15 | AAPL | SELL | 5 | bearish |"
    with patch("src.backtest.yf") as mock_yf:
        mock_yf.Ticker.return_value.history.return_value = _fake_hist(100.0, 110.0)
        result = process_backtest_row(line)

    assert result["roi"] == pytest.approx(-10.0)


def test_summarize_backtest():
    results = [
        {"action": "BUY", "roi": 10.0},
        {"action": "BUY", "roi": -5.0},
        {"action": "HOLD", "roi": 0.0},
    ]
    summary = summarize_backtest(results)

    assert summary["actionable"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["avg_roi"] == pytest.approx(2.5)


def test_load_backtest_results_empty(tmp_path):
    log_path = tmp_path / "empty.md"
    log_path.write_text("# empty\n", encoding="utf-8")
    assert load_backtest_results(str(log_path)) == []


def _fake_hist(start: float, end: float):
    import pandas as pd

    return pd.DataFrame(
        {"Close": [start, end]},
        index=pd.to_datetime(["2024-01-15", "2024-01-22"]),
    )
