from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import feedparser
import pandas as pd
import yfinance as yf
from stockstats import StockDataFrame

logger = logging.getLogger(__name__)


def get_price_data(ticker: str, end_date: str, days_back: int = 365) -> pd.DataFrame:
    from datetime import datetime, timedelta

    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = end - timedelta(days=days_back)

    stock = yf.Ticker(ticker)
    df = stock.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

    if df.empty:
        return df

    try:
        sdf = StockDataFrame.retype(df.copy())
        df["rsi"] = sdf["rsi_14"]
        df["macd"] = sdf["macd"]
        df["macds"] = sdf["macds"]
        df["boll"] = sdf["boll"]
    except Exception as exc:
        logger.debug("Technical indicator calculation failed for %s: %s", ticker, exc)

    return df


def sanitize_data(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): sanitize_data(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize_data(x) for x in o]
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "item"):
        return o.item()
    return o


def get_financials(ticker: str) -> Dict:
    stock = yf.Ticker(ticker)
    income_stmt = stock.income_stmt
    balance_sheet = stock.balance_sheet
    cashflow = stock.cashflow

    data: Dict[str, Any] = {
        "info": stock.info or {},
        "income_stmt": income_stmt.to_dict() if income_stmt is not None and not income_stmt.empty else {},
        "balance_sheet": balance_sheet.to_dict() if balance_sheet is not None and not balance_sheet.empty else {},
        "cashflow": cashflow.to_dict() if cashflow is not None and not cashflow.empty else {},
    }
    return sanitize_data(data)


def get_news(ticker: str) -> List[Dict]:
    stock = yf.Ticker(ticker)
    news: List[Dict[str, Any]] = sanitize_data(stock.news or [])

    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    ]

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                news.append({
                    "title": entry.get("title", ""),
                    "publisher": "RSS",
                    "link": entry.get("link", ""),
                })
        except Exception as exc:
            logger.debug("RSS feed %s failed: %s", url, exc)

    return news


def get_reddit_wsb(ticker: str) -> List[Dict]:
    url = f"https://www.reddit.com/r/wallstreetbets/search.rss?q={ticker}&restrict_sr=1&sort=new"
    posts: List[Dict[str, Any]] = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            posts.append({
                "title": entry.get("title", ""),
                "publisher": "r/WallStreetBets",
                "link": entry.get("link", ""),
            })
    except Exception as exc:
        logger.debug("Reddit WSB feed failed for %s: %s", ticker, exc)
    return posts
