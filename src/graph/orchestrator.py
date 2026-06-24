from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.analysts import AnalystTeam
from src.agents.decision_makers import DecisionTeam
from src.config import config
from src.data.logger import get_recent_logs, log_decision
from src.data.market_data import get_financials, get_news, get_price_data, get_reddit_wsb, sanitize_data
from src.state import TradingState

logger = logging.getLogger(__name__)


def build_graph():
    graph = StateGraph(TradingState)

    analysts = AnalystTeam()
    decision_makers = DecisionTeam()

    def fetch_data_node(state: TradingState) -> Dict[str, Any]:
        from src.portfolio import check_stop_losses
        import yfinance as yf

        ticker = state["ticker"]

        try:
            current_price = yf.Ticker(ticker).fast_info.get("lastPrice")
            if current_price:
                sells = check_stop_losses({ticker: current_price})
                for sell_ticker, drop in sells:
                    logger.info("STOP LOSS TRIGGERED for %s: Dropped %.1f%%", sell_ticker, drop * 100)
        except Exception as exc:
            logger.warning("Stop loss check failed: %s", exc)

        target_date = state.get("target_date", "")
        price_df = get_price_data(ticker, target_date)
        price_json = sanitize_data(price_df.tail(30).to_dict("index"))
        return {
            "price_data": price_json,
            "fundamental_data": get_financials(ticker),
            "news_data": get_news(ticker),
            "reddit_data": get_reddit_wsb(ticker),
        }

    def reflection_node(state: TradingState) -> Dict[str, Any]:
        logs = get_recent_logs(state["ticker"])
        existing_bull = state.get("bull_arguments") or ""
        return {"bull_arguments": f"PAST CONTEXT:\n{logs}\n\n{existing_bull}"}

    def fundamental_node(state: TradingState) -> Dict[str, Any]:
        return {"fundamental_analysis": analysts.analyze_fundamentals(state)}

    def technical_node(state: TradingState) -> Dict[str, Any]:
        return {"technical_analysis": analysts.analyze_technicals(state)}

    def sentiment_node(state: TradingState) -> Dict[str, Any]:
        return {"sentiment_analysis": analysts.analyze_sentiment(state)}

    def debate_node(state: TradingState) -> Dict[str, Any]:
        bull, bear = decision_makers.debate_research(state)
        return {"bull_arguments": bull, "bear_arguments": bear}

    def risk_node(state: TradingState) -> Dict[str, Any]:
        return {"risk_assessment": decision_makers.assess_risk(state)}

    def portfolio_node(state: TradingState) -> Dict[str, Any]:
        decision = decision_makers.make_portfolio_decision(state)
        log_decision(state["ticker"], state.get("target_date", ""), decision)
        return {"final_decision": decision}

    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("technical", technical_node)
    graph.add_node("sentiment", sentiment_node)
    graph.add_node("debate", debate_node)
    graph.add_node("risk", risk_node)
    graph.add_node("portfolio", portfolio_node)

    graph.add_edge(START, "fetch_data")
    graph.add_edge("fetch_data", "reflection")
    graph.add_edge("reflection", "fundamental")
    graph.add_edge("reflection", "technical")
    graph.add_edge("reflection", "sentiment")
    graph.add_edge(["fundamental", "technical", "sentiment"], "debate")
    graph.add_edge("debate", "risk")
    graph.add_edge("risk", "portfolio")
    graph.add_edge("portfolio", END)

    memory = MemorySaver()

    return graph.compile(checkpointer=memory)
