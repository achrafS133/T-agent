from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from src.config import config
from src.state import TradingState


class AnalystTeam:
    def __init__(self) -> None:
        self.llm = config.get_llm()

    def analyze_fundamentals(self, state: TradingState) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert Fundamental Analyst. Analyze the financial data and provide a concise summary of the company's financial health, valuation, and growth prospects. Structure your response with clear sections: Valuation, Growth, Risks, and a 1-sentence verdict."),
            ("user", "Ticker: {ticker}\nFundamental Data: {fundamental_data}")
        ])
        chain = prompt | self.llm
        result = chain.invoke({
            "ticker": state["ticker"],
            "fundamental_data": str(state.get("fundamental_data") or "")[:2000]
        })
        return result.content

    def analyze_technicals(self, state: TradingState) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert Technical Analyst. Review the recent price data AND technical indicators (RSI, MACD, Bollinger Bands). Identify trends, overbought/oversold conditions, and key support/resistance levels. End with a TECHNICAL VERDICT: BULLISH/BEARISH/NEUTRAL."),
            ("user", "Ticker: {ticker}\nTarget Date: {target_date}\nPrice & Indicator Data: {price_data}")
        ])
        chain = prompt | self.llm
        result = chain.invoke({
            "ticker": state["ticker"],
            "target_date": state.get("target_date", ""),
            "price_data": str(state.get("price_data") or "")[:3000]
        })
        return result.content

    def analyze_sentiment(self, state: TradingState) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert Sentiment Analyst. Review the recent news headlines AND Reddit posts to summarize market sentiment. YOU MUST ASSIGN A SENTIMENT SCORE from 1 to 10 (1 = Extreme Bearish, 10 = Extreme Bullish). Factor meme potential from Reddit chatter. Format: 'SCORE: X/10' then reasoning."),
            ("user", "Ticker: {ticker}\nNews Data: {news_data}\nReddit Data: {reddit_data}")
        ])
        chain = prompt | self.llm
        result = chain.invoke({
            "ticker": state["ticker"],
            "news_data": str(state.get("news_data") or ""),
            "reddit_data": str(state.get("reddit_data") or [])
        })
        return result.content
