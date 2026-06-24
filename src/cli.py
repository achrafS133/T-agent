from __future__ import annotations

import argparse
import logging
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.graph.orchestrator import build_graph
from src.logging_config import setup_logging

console = Console()
logger = logging.getLogger(__name__)


def run_cli() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="T-AGENT PRO — Multi-Agent Trading Intelligence Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ticker", type=str, required=True, help="Stock ticker symbol (e.g. AAPL, NVDA, BTC-USD)")
    parser.add_argument("--date", type=str, default=datetime.today().strftime("%Y-%m-%d"), help="Target date YYYY-MM-DD")
    parser.add_argument("--risk", type=str, default="conservative", choices=["conservative", "aggressive"], help="Risk profile")
    parser.add_argument("--persona", type=str, default="standard", help="Decision persona")

    args = parser.parse_args()

    console.print(Panel(
        f"[bold]T-AGENT PRO[/bold] — Initializing analysis for [cyan]{args.ticker}[/cyan] on [dim]{args.date}[/dim]",
        style="blue",
    ))

    app = build_graph()
    initial_state = {
        "ticker": args.ticker,
        "target_date": args.date,
        "risk_level": args.risk,
        "persona": args.persona,
    }

    run_config = {"configurable": {"thread_id": f"{args.ticker}_{args.date}"}}

    try:
        for state in app.stream(initial_state, run_config):
            for node_name, node_state in state.items():
                console.print(f"[bold green]  [*][/bold green] Node [cyan]`{node_name}`[/cyan] completed")
                if "risk" in node_name:
                    console.print(f"[dim]    {node_state.get('risk_assessment', '')[:200]}[/dim]")

        final_state = app.get_state(run_config).values
        decision = final_state.get("final_decision") or {}

        action = decision.get("action", "N/A")
        action_color = "green" if action == "BUY" else "red" if action == "SELL" else "yellow"

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[bold]Action[/bold]", f"[{action_color}]{action}[/{action_color}]")
        table.add_row("[bold]Quantity[/bold]", str(decision.get("quantity", 0)))
        table.add_row("[bold]Confidence[/bold]", str(decision.get("confidence", "N/A")))
        table.add_row("[bold]Reasoning[/bold]", str(decision.get("reasoning", "N/A"))[:300])

        console.print()
        console.print(Panel(table, title=f"[bold]Decision: {args.ticker}[/bold]", style="magenta"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user.[/yellow]")
    except Exception as exc:
        console.print(f"[bold red]Error: {exc}[/bold red]")
        logger.exception("Analysis failed")


if __name__ == "__main__":
    run_cli()
