import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance

from moggy.data import DataError


@dataclass
class FundamentalsData:
    ticker: str
    pe_ratio: float | None
    revenue_growth: float | None
    gross_margin: float | None
    debt_to_equity: float | None


@dataclass
class NewsItem:
    title: str
    publisher: str
    link: str
    published_at: datetime


class MarketClient:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Any] = {}
        self._locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get_fundamentals(self, ticker: str) -> FundamentalsData | DataError:
        cache_key = (ticker, "get_fundamentals")
        if cache_key in self._cache:
            return self._cache[cache_key]
        async with self._locks[cache_key]:
            if cache_key in self._cache:
                return self._cache[cache_key]
            try:

                def _fetch_info() -> dict[str, Any]:
                    return yfinance.Ticker(ticker).info

                info = await asyncio.to_thread(_fetch_info)
                result = FundamentalsData(
                    ticker=ticker,
                    pe_ratio=info.get("trailingPE"),
                    revenue_growth=info.get("revenueGrowth"),
                    gross_margin=info.get("grossMargins"),
                    debt_to_equity=info.get("debtToEquity"),
                )
                self._cache[cache_key] = result
                return result
            except Exception as e:
                return DataError(source="yfinance", message=str(e))

    async def get_ohlcv(self, ticker: str, period: str = "6mo") -> pd.DataFrame | DataError:
        cache_key = (ticker, f"get_ohlcv:{period}")
        if cache_key in self._cache:
            return self._cache[cache_key]
        async with self._locks[cache_key]:
            if cache_key in self._cache:
                return self._cache[cache_key]
            try:

                def _fetch_history() -> pd.DataFrame:
                    return yfinance.Ticker(ticker).history(period=period)

                df = await asyncio.to_thread(_fetch_history)
                if df.empty:
                    return DataError(source="yfinance", message=f"No OHLCV data for {ticker}")
                self._cache[cache_key] = df
                return df
            except Exception as e:
                return DataError(source="yfinance", message=str(e))

    async def get_news(self, ticker: str, limit: int = 10) -> list[NewsItem] | DataError:
        cache_key = (ticker, "get_news")
        if cache_key in self._cache:
            return self._cache[cache_key][:limit]
        async with self._locks[cache_key]:
            if cache_key in self._cache:
                return self._cache[cache_key][:limit]
            try:

                def _fetch_news() -> list[dict[str, Any]]:
                    return yfinance.Ticker(ticker).news

                raw = await asyncio.to_thread(_fetch_news)
                items: list[NewsItem] = []
                for item in raw:
                    content = item.get("content", {})
                    pub_date_str = content.get("pubDate", "")
                    try:
                        published_at = datetime.fromisoformat(pub_date_str)
                    except (ValueError, TypeError):
                        published_at = datetime(1970, 1, 1, tzinfo=UTC)
                    items.append(
                        NewsItem(
                            title=content.get("title", ""),
                            publisher=content.get("provider", {}).get("displayName", ""),
                            link=content.get("canonicalUrl", {}).get("url", ""),
                            published_at=published_at,
                        )
                    )
                self._cache[cache_key] = items
                return items[:limit]
            except Exception as e:
                return DataError(source="yfinance", message=str(e))
