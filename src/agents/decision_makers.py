from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

import yfinance as yf
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.config import config
from src.state import TradingState

logger = logging.getLogger(__name__)


class FinalDecisionStructure(BaseModel):
    action: str = Field(description="Action to take: BUY, SELL, or HOLD")
    quantity: int = Field(description="Percentage or number of shares to allocate/trade, 0 if HOLD")
    confidence: str = Field(description="Confidence Level: Low, Medium, High")
    reasoning: str = Field(description="Detailed reasoning for the decision")


class DecisionTeam:
    def __init__(self) -> None:
        self.llm = config.get_llm()
        self.llm_debate = None
        try:
            self.llm_debate = config.get_llm().__class__(
                model=self.llm.model,
                api_key=self.llm.openai_api_key if hasattr(self.llm, "openai_api_key") else None,
                temperature=0.2,
            )
        except Exception:
            self.llm_debate = self.llm
        self.structured_llm = config.get_structured_llm(FinalDecisionStructure)

    def debate_research(self, state: TradingState) -> Tuple[str, str]:
        llm = self.llm_debate or self.llm

        prompt_bull = ChatPromptTemplate.from_messages([
            ("system",
             "You are a Bullish Researcher using SECOND-ORDER THINKING. Ask: 'If X happens, who else benefits?' Synthesize the strongest argument to BUY, highlighting non-obvious indirect opportunities."),
            ("user", "Fundamental: {fund}\nTechnical: {tech}\nSentiment: {sent}")
        ])
        chain_bull = prompt_bull | llm
        bull_arg = chain_bull.invoke({
            "fund": state.get("fundamental_analysis") or "",
            "tech": state.get("technical_analysis") or "",
            "sent": state.get("sentiment_analysis") or ""
        }).content

        prompt_bear = ChatPromptTemplate.from_messages([
            ("system",
             "You are a Bearish Researcher using SECOND-ORDER THINKING. Ask: 'If X happens, who else suffers?' Synthesize the strongest argument to SELL, highlighting non-obvious indirect risks."),
            ("user", "Fundamental: {fund}\nTechnical: {tech}\nSentiment: {sent}")
        ])
        chain_bear = prompt_bear | llm
        bear_arg = chain_bear.invoke({
            "fund": state.get("fundamental_analysis") or "",
            "tech": state.get("technical_analysis") or "",
            "sent": state.get("sentiment_analysis") or ""
        }).content

        return bull_arg, bear_arg

    def assess_risk(self, state: TradingState) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are the Risk Manager. Evaluate bull/bear arguments and assign a risk level (Low, Medium, High). If sentiment is extreme (1 or 10), flag as HIGH RISK and recommend blocking trades to prevent FOMO or panic. End with 'RISK LEVEL: Low/Medium/High'."),
            ("user", "Bull Argument: {bull}\nBear Argument: {bear}")
        ])
        chain = prompt | self.llm
        result = chain.invoke({
            "bull": state.get("bull_arguments") or "",
            "bear": state.get("bear_arguments") or ""
        })
        return result.content

    def make_portfolio_decision(self, state: TradingState) -> Dict[str, Any]:
        risk_level = state.get("risk_level", "conservative")
        risk_context = (
            "Act AGGRESSIVELY: Look for high ROI, larger positions, and higher risk tolerance."
            if risk_level == "aggressive"
            else "Act CONSERVATIVELY: Prioritize capital preservation, small positions, and strict risk management."
        )

        persona = state.get("persona") or "standard"
        persona_map = {
            "Warren Buffett (Value)": "You are Warren Buffett. Ignore hype and memes. Focus strictly on fundamentals, cash flow, and value. Reject risky or speculative insights.",
            "WSB Degen": "You are a WallStreetBets Degen. You love momentum, meme stocks, Reddit hype, and aggressive YOLO trades. You embrace risky human insights.",
            "The Quant": "You are a cold, calculating Quant. Ignore news, rumors, and human feelings entirely. Strictly follow technical indicators and data.",
        }
        persona_context = persona_map.get(persona, "You are a balanced standard portfolio manager.")

        human_insight = state.get("human_insight") or ""
        human_context = (
            f"\nHuman Insight Override: {human_insight}\n(Evaluate if this insight aligns with your persona before acting on it.)"
            if human_insight else ""
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             f"{persona_context} {risk_context} Decide whether to BUY, SELL, or HOLD. Provide your action, quantity/allocation (1-10), confidence level, and detailed reasoning. ONLY execute BUY/SELL if Confidence is HIGH and Risk is not extreme. You MUST explicitly address the Human Insight if it was provided."),
            ("user",
             f"Ticker: {{ticker}}\nBull Case (with context): {{bull}}\nBear Case: {{bear}}\nRisk Assessment: {{risk}}{human_context}")
        ])
        chain = prompt | self.structured_llm
        result = chain.invoke({
            "ticker": state["ticker"],
            "bull": state.get("bull_arguments") or "",
            "bear": state.get("bear_arguments") or "",
            "risk": state.get("risk_assessment") or ""
        })
        decision = result.model_dump()

        try:
            from src.portfolio import update_portfolio

            ticker = state["ticker"]
            price = yf.Ticker(ticker).fast_info.get("lastPrice")
            if price is None:
                raise ValueError(f"Could not get current price for {ticker}")

            action = decision.get("action")
            qty = int(decision.get("quantity", 0))
            confidence = decision.get("confidence", "Low")

            if action in ("BUY", "SELL") and qty > 0 and confidence.upper() == "HIGH":
                success, msg = update_portfolio(ticker, action, qty, price)
                if not success:
                    decision["reasoning"] += f" [TRADE FAILED: {msg}]"
                    decision["action"] = "HOLD"
                    decision["quantity"] = 0
            elif action in ("BUY", "SELL") and confidence.upper() != "HIGH":
                decision["reasoning"] += f" [TRADE BLOCKED: Confidence was {confidence}, requires HIGH]"
                decision["action"] = "HOLD"
                decision["quantity"] = 0
        except Exception as exc:
            logger.warning("Portfolio update failed: %s", exc)

        return decision
