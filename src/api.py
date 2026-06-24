from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import config
from src.graph.orchestrator import build_graph
from src.logging_config import setup_logging
from src.portfolio import get_pnl_history, get_portfolio
from src.backtest import load_backtest_results, summarize_backtest

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="T-AGENT PRO API",
    description="Multi-Agent Trading Intelligence API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_LABELS = {
    "fetch_data": "Fetching market data & checking stop-losses",
    "reflection": "Loading past decision context",
    "fundamental": "Fundamental analyst reviewing financials",
    "technical": "Technical analyst reviewing indicators",
    "sentiment": "Sentiment analyst scanning news & Reddit",
    "debate": "Bull vs bear research debate",
    "risk": "Risk manager evaluating exposure",
    "portfolio": "Portfolio manager making final decision",
}


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str) -> None:
        payload = json.dumps({"message": message})
        stale: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                stale.append(connection)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


class AnalyzeRequest(BaseModel):
    risk_level: str = "conservative"
    persona: str = "standard"
    human_insight: str = ""
    target_date: str = Field(default_factory=lambda: datetime.today().strftime("%Y-%m-%d"))


def _notify(loop: asyncio.AbstractEventLoop, message: str) -> None:
    asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)


def _run_analysis_sync(ticker: str, req: AnalyzeRequest, loop: asyncio.AbstractEventLoop) -> None:
    graph = build_graph()
    initial_state: Dict[str, Any] = {
        "ticker": ticker,
        "target_date": req.target_date,
        "risk_level": req.risk_level,
        "persona": req.persona,
        "human_insight": req.human_insight,
    }

    _notify(loop, f"Starting analysis for {ticker} ({req.risk_level} | {req.persona})")
    logger.info("Starting analysis for %s (%s | %s)", ticker, req.risk_level, req.persona)

    try:
        for state in graph.stream(initial_state, config={"configurable": {"thread_id": f"web_{ticker}"}}):
            for node_name in state:
                label = NODE_LABELS.get(node_name, node_name)
                _notify(loop, f"[{node_name}] {label} — completed")
                logger.info("Node `%s` completed", node_name)

        final = graph.get_state({"configurable": {"thread_id": f"web_{ticker}"}}).values
        decision = final.get("final_decision") or {}
        action = decision.get("action", "N/A")
        qty = decision.get("quantity", 0)
        _notify(loop, f"Analysis complete for {ticker}: {action} x{qty}")
    except Exception as exc:
        logger.error("Analysis error for %s: %s", ticker, exc)
        _notify(loop, f"Analysis failed for {ticker}: {exc}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/history")
async def get_history() -> Dict[str, Any]:
    import os

    log_path = os.path.join(config.LOG_DIR, "decision_history.md")
    if not os.path.exists(log_path):
        return {"history": []}
    history: List[Dict[str, str]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "|" not in line or "Ticker" in line or "---" in line:
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 5:
                history.append({
                    "date": parts[0],
                    "ticker": parts[1],
                    "action": parts[2],
                    "quantity": parts[3],
                    "reasoning": parts[4],
                })
    return {"history": list(reversed(history))}


@app.get("/api/portfolio")
async def get_port() -> Dict[str, Any]:
    portfolio = get_portfolio()
    total_holdings_value = sum(
        h["qty"] * h["avg_price"] for h in portfolio["holdings"].values()
    )
    portfolio["total_value"] = portfolio["cash"] + total_holdings_value
    portfolio["holdings_value"] = total_holdings_value
    portfolio["pnl"] = portfolio["total_value"] - config.INITIAL_CASH
    portfolio["pnl_pct"] = ((portfolio["total_value"] / config.INITIAL_CASH) - 1) * 100
    return portfolio


@app.post("/api/analyze/{ticker}")
async def trigger_analysis(ticker: str, req: AnalyzeRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    loop = asyncio.get_running_loop()
    background_tasks.add_task(_run_analysis_sync, ticker.upper(), req, loop)
    return {"status": "Analysis started", "ticker": ticker.upper()}


@app.get("/api/portfolio/pnl-history")
async def get_pnl_history_endpoint() -> Dict[str, Any]:
    history = get_pnl_history()
    return {"history": history, "initial_cash": config.INITIAL_CASH}


@app.get("/api/backtest")
async def get_backtest() -> Dict[str, Any]:
    results = load_backtest_results()
    return {"results": results, "summary": summarize_backtest(results)}


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "provider": config.LLM_PROVIDER,
        "model": config.LLM_MODEL if config.LLM_PROVIDER != "ollama" else config.OLLAMA_MODEL,
    }
