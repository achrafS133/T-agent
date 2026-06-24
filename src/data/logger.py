from __future__ import annotations

import os
from typing import List

from src.config import config


LOG_DIR = config.LOG_DIR


def log_decision(ticker: str, date: str, decision: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, "decision_history.md")

    exists = os.path.exists(log_path)

    with open(log_path, "a", encoding="utf-8") as f:
        if not exists:
            f.write("# Trading Decision History\n\n")
            f.write("| Date | Ticker | Action | Quantity | Reasoning |\n")
            f.write("|------|--------|--------|----------|-----------|\n")

        action = decision.get("action", "N/A")
        qty = decision.get("quantity", 0)
        reason = str(decision.get("reasoning") or "N/A").replace("\n", " ").replace("|", "\\|")

        f.write(f"| {date} | {ticker} | {action} | {qty} | {reason} |\n")


def get_recent_logs(ticker: str, limit: int = 5) -> str:
    log_path = os.path.join(LOG_DIR, "decision_history.md")
    if not os.path.exists(log_path):
        return "No previous logs found."

    relevant_lines: List[str] = []
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in reversed(lines):
            if f"| {ticker} |" in line:
                relevant_lines.append(line.strip())
                if len(relevant_lines) >= limit:
                    break

    if not relevant_lines:
        return f"No previous logs found for ticker {ticker}."

    return "\n".join(relevant_lines)
