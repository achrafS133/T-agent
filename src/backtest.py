from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf
from rich.console import Console
from rich.table import Table

from src.config import config

console = Console()
logger = logging.getLogger(__name__)


def process_backtest_row(line: str) -> Optional[Dict[str, Any]]:
    if "|" not in line or "Ticker" in line or "---" in line:
        return None

    parts = [p.strip() for p in line.split("|") if p.strip()]
    if len(parts) < 3:
        return None

    date_str, ticker, action = parts[0], parts[1], parts[2]

    try:
        start_date = datetime.strptime(date_str, "%Y-%m-%d")
        end_date = start_date + timedelta(days=7)

        stock = yf.Ticker(ticker)
        hist = stock.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
        )

        if hist.empty:
            return None

        start_price = float(hist.iloc[0]["Close"])
        end_price = float(hist.iloc[-1]["Close"])

        if start_price == 0:
            return None

        raw_roi = ((end_price - start_price) / start_price) * 100

        if action == "BUY":
            roi = raw_roi
        elif action == "SELL":
            roi = -raw_roi
        else:
            roi = 0.0

        return {
            "date": date_str,
            "ticker": ticker,
            "action": action,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "roi": round(roi, 2),
        }
    except Exception as exc:
        logger.debug("Error processing %s on %s: %s", ticker, date_str, exc)
        return None


def load_backtest_results(log_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = log_path or os.path.join(config.LOG_DIR, "decision_history.md")
    if not os.path.exists(path):
        return []

    results: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            row = process_backtest_row(line)
            if row:
                results.append(row)
    return results


def summarize_backtest(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    actionable = [r for r in results if r["action"] in ("BUY", "SELL")]
    if not actionable:
        return {
            "total": len(results),
            "actionable": 0,
            "avg_roi": 0.0,
            "win_rate": 0.0,
            "wins": 0,
            "losses": 0,
        }

    wins = sum(1 for r in actionable if r["roi"] > 0)
    losses = sum(1 for r in actionable if r["roi"] < 0)
    avg_roi = sum(r["roi"] for r in actionable) / len(actionable)

    return {
        "total": len(results),
        "actionable": len(actionable),
        "avg_roi": round(avg_roi, 2),
        "win_rate": round((wins / len(actionable)) * 100, 1),
        "wins": wins,
        "losses": losses,
    }


def run_backtest() -> None:
    results = load_backtest_results()
    if not results:
        console.print("[red]No decision logs found to backtest.[/red]")
        return

    console.print("[bold blue]Starting Backtest for Logged Decisions...[/bold blue]")

    table = Table(title="Backtest Results (ROI after 7 days)")
    table.add_column("Date", style="cyan")
    table.add_column("Ticker", style="magenta")
    table.add_column("Action", style="green")
    table.add_column("Start Price")
    table.add_column("End Price (7d)")
    table.add_column("ROI (%)", justify="right")

    for row in results:
        roi_color = "green" if row["roi"] > 0 else "red" if row["roi"] < 0 else "white"
        table.add_row(
            row["date"],
            row["ticker"],
            row["action"],
            f"{row['start_price']:.2f}",
            f"{row['end_price']:.2f}",
            f"[{roi_color}]{row['roi']:.2f}%[/{roi_color}]",
        )

    summary = summarize_backtest(results)
    console.print(table)
    console.print(
        f"\n[dim]Actionable: {summary['actionable']} | "
        f"Avg ROI: {summary['avg_roi']}% | "
        f"Win rate: {summary['win_rate']}%[/dim]"
    )


if __name__ == "__main__":
    run_backtest()
