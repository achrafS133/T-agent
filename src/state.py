from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class TradingState(TypedDict, total=False):
    ticker: str
    target_date: str
    risk_level: str
    persona: str
    human_insight: str

    price_data: Optional[Dict[str, Any]]
    news_data: Optional[List[Dict[str, Any]]]
    reddit_data: Optional[List[Dict[str, Any]]]
    fundamental_data: Optional[Dict[str, Any]]

    technical_analysis: Optional[str]
    fundamental_analysis: Optional[str]
    sentiment_analysis: Optional[str]

    bull_arguments: Optional[str]
    bear_arguments: Optional[str]

    risk_assessment: Optional[str]
    final_decision: Optional[Dict[str, Any]]

    errors: Optional[List[str]]
