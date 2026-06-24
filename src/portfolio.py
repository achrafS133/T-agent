from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from src.config import config


PORTFOLIO_FILE = os.path.join(config.LOG_DIR, "portfolio.json")


def _ensure_log_dir() -> None:
    os.makedirs(config.LOG_DIR, exist_ok=True)


def _portfolio_totals(portfolio: Dict) -> Tuple[float, float, float, float]:
    holdings_value = sum(h["qty"] * h["avg_price"] for h in portfolio["holdings"].values())
    total_value = portfolio["cash"] + holdings_value
    pnl = total_value - config.INITIAL_CASH
    pnl_pct = ((total_value / config.INITIAL_CASH) - 1) * 100 if config.INITIAL_CASH else 0.0
    return total_value, holdings_value, pnl, pnl_pct


def _record_snapshot(portfolio: Dict) -> None:
    total_value, _, pnl, pnl_pct = _portfolio_totals(portfolio)
    portfolio.setdefault("snapshots", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_value": round(total_value, 2),
        "cash": round(portfolio["cash"], 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
    })


def initialize_portfolio() -> None:
    _ensure_log_dir()
    if not os.path.exists(PORTFOLIO_FILE):
        initial_data: Dict[str, Any] = {
            "cash": config.INITIAL_CASH,
            "holdings": {},
            "history": [],
            "snapshots": [],
        }
        _record_snapshot(initial_data)
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, indent=2)


def get_portfolio() -> Dict:
    initialize_portfolio()
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        portfolio = json.load(f)
    if "snapshots" not in portfolio:
        portfolio["snapshots"] = []
        _record_snapshot(portfolio)
        _save_portfolio(portfolio)
    return portfolio


def get_pnl_history() -> List[Dict[str, Any]]:
    portfolio = get_portfolio()
    snapshots = portfolio.get("snapshots", [])
    if snapshots:
        return snapshots

    return [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_value": config.INITIAL_CASH,
        "cash": config.INITIAL_CASH,
        "pnl": 0.0,
        "pnl_pct": 0.0,
    }]


def _save_portfolio(portfolio: Dict) -> None:
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)


def update_portfolio(ticker: str, action: str, quantity: int, price: float) -> Tuple[bool, str]:
    portfolio = get_portfolio()

    cost = quantity * price
    fee = cost * config.BROKER_FEE_PCT
    total_cost = cost + fee

    total_portfolio_value = portfolio["cash"] + sum(
        h["qty"] * h["avg_price"] for h in portfolio["holdings"].values()
    )
    max_position_size = total_portfolio_value * config.MAX_POSITION_PCT
    min_cash_reserve = total_portfolio_value * config.MIN_CASH_RESERVE_PCT

    if action == "BUY":
        current_holding = portfolio["holdings"].get(ticker, {"qty": 0, "avg_price": 0.0})
        projected_position_size = (current_holding["qty"] * current_holding["avg_price"]) + cost

        if portfolio["cash"] - total_cost < min_cash_reserve:
            return False, f"Violates {config.MIN_CASH_RESERVE_PCT * 100:.0f}% minimum cash reserve rule."

        if projected_position_size > max_position_size:
            return False, f"Position exceeds {config.MAX_POSITION_PCT * 100:.0f}% max allocation rule."

        if portfolio["cash"] >= total_cost:
            portfolio["cash"] -= total_cost
            total_qty = current_holding["qty"] + quantity
            new_avg = ((current_holding["qty"] * current_holding["avg_price"]) + cost) / total_qty
            portfolio["holdings"][ticker] = {"qty": total_qty, "avg_price": round(new_avg, 4)}
        else:
            return False, "Insufficient funds (including fees)"

    elif action == "SELL":
        current_holding = portfolio["holdings"].get(ticker, {"qty": 0, "avg_price": 0.0})
        if current_holding["qty"] >= quantity:
            portfolio["cash"] += cost - fee
            current_holding["qty"] -= quantity
            if current_holding["qty"] == 0:
                del portfolio["holdings"][ticker]
            else:
                portfolio["holdings"][ticker] = current_holding
        else:
            return False, "Insufficient shares"

    else:
        return False, f"Unknown action: {action}"

    portfolio["history"].append({
        "ticker": ticker,
        "action": action,
        "quantity": quantity,
        "price": round(price, 4),
        "fee": round(fee, 4),
    })

    _record_snapshot(portfolio)
    _save_portfolio(portfolio)
    return True, "Success"


def check_stop_losses(current_prices: Dict[str, float]) -> List[Tuple[str, float]]:
    portfolio = get_portfolio()
    sells_executed: List[Tuple[str, float]] = []

    for ticker, holding in list(portfolio["holdings"].items()):
        if ticker in current_prices:
            curr_price = current_prices[ticker]
            if holding["avg_price"] <= 0:
                continue
            drop = (holding["avg_price"] - curr_price) / holding["avg_price"]
            if drop >= config.STOP_LOSS_PCT:
                qty = holding["qty"]
                cost = qty * curr_price
                fee = cost * config.BROKER_FEE_PCT
                portfolio["cash"] += cost - fee
                del portfolio["holdings"][ticker]
                portfolio["history"].append({
                    "ticker": ticker,
                    "action": "STOP_LOSS_SELL",
                    "quantity": qty,
                    "price": round(curr_price, 4),
                    "fee": round(fee, 4),
                    "reason": f"Auto-sell: dropped {drop * 100:.1f}% from avg purchase price.",
                })
                sells_executed.append((ticker, drop))

    if sells_executed:
        _record_snapshot(portfolio)
        _save_portfolio(portfolio)

    return sells_executed
