import asyncio

import pandas as pd
import pytest

from moggy.data import DataError
from moggy.data.market import FundamentalsData, MarketClient, NewsItem


@pytest.fixture
def mock_info():
    return {
        "trailingPE": 25.5,
        "revenueGrowth": 0.12,
        "grossMargins": 0.45,
        "debtToEquity": 1.2,
    }


@pytest.fixture
def mock_ohlcv():
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 100.0],
            "Close": [102.0, 103.0],
            "Volume": [1_000_000, 1_100_000],
        }
    )


@pytest.fixture
def mock_news_raw():
    """yfinance 1.3.0 schema: top-level keys are id + content."""
    return [
        {
            "id": "uuid-1",
            "content": {
                "title": "Apple reports strong Q1",
                "pubDate": "2024-01-01T00:00:00Z",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://reuters.com/article1"},
            },
        },
        {
            "id": "uuid-2",
            "content": {
                "title": "iPhone sales surge",
                "pubDate": "2024-01-02T00:00:00Z",
                "provider": {"displayName": "Bloomberg"},
                "canonicalUrl": {"url": "https://bloomberg.com/article2"},
            },
        },
        {
            "id": "uuid-3",
            "content": {
                "title": "Services revenue grows",
                "pubDate": "2024-01-03T00:00:00Z",
                "provider": {"displayName": "CNBC"},
                "canonicalUrl": {"url": "https://cnbc.com/article3"},
            },
        },
    ]


def _patch_ticker(mocker, info=None, history_df=None, news=None):
    ticker_instance = mocker.MagicMock()
    ticker_instance.info = info if info is not None else {}
    ticker_instance.history.return_value = history_df if history_df is not None else pd.DataFrame()
    ticker_instance.news = news if news is not None else []
    return mocker.patch("yfinance.Ticker", return_value=ticker_instance)


# ---------------------------------------------------------------------------
# get_fundamentals
# ---------------------------------------------------------------------------


class TestGetFundamentals:
    async def test_returns_fundamentals_data(self, mocker, mock_info):
        _patch_ticker(mocker, info=mock_info)
        client = MarketClient()
        result = await client.get_fundamentals("AAPL")
        assert isinstance(result, FundamentalsData)
        assert result.ticker == "AAPL"
        assert result.pe_ratio == 25.5
        assert result.revenue_growth == 0.12
        assert result.gross_margin == 0.45
        assert result.debt_to_equity == 1.2

    async def test_missing_fields_are_none(self, mocker):
        _patch_ticker(mocker, info={})
        client = MarketClient()
        result = await client.get_fundamentals("AAPL")
        assert isinstance(result, FundamentalsData)
        assert result.pe_ratio is None
        assert result.revenue_growth is None
        assert result.gross_margin is None
        assert result.debt_to_equity is None

    async def test_returns_data_error_on_exception(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=RuntimeError("network error"))
        client = MarketClient()
        result = await client.get_fundamentals("AAPL")
        assert isinstance(result, DataError)
        assert result.source == "yfinance"
        assert "network error" in result.message

    async def test_returns_data_error_when_info_attr_raises(self, mocker):
        ticker_inst = mocker.MagicMock()
        type(ticker_inst).info = mocker.PropertyMock(side_effect=RuntimeError("malformed response"))
        mocker.patch("yfinance.Ticker", return_value=ticker_inst)
        client = MarketClient()
        result = await client.get_fundamentals("AAPL")
        assert isinstance(result, DataError)

    async def test_never_raises(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=Exception("boom"))
        client = MarketClient()
        result = await client.get_fundamentals("AAPL")
        assert isinstance(result, DataError)

    async def test_cache_hit_skips_second_yfinance_call(self, mocker, mock_info):
        mock_yfin = _patch_ticker(mocker, info=mock_info)
        client = MarketClient()
        await client.get_fundamentals("AAPL")
        await client.get_fundamentals("AAPL")
        assert mock_yfin.call_count == 1

    async def test_different_tickers_not_shared_in_cache(self, mocker, mock_info):
        mock_yfin = _patch_ticker(mocker, info=mock_info)
        client = MarketClient()
        await client.get_fundamentals("AAPL")
        await client.get_fundamentals("MSFT")
        assert mock_yfin.call_count == 2

    async def test_concurrent_same_ticker_hits_yfinance_once(self, mocker, mock_info):
        mock_yfin = _patch_ticker(mocker, info=mock_info)
        client = MarketClient()
        results = await asyncio.gather(
            client.get_fundamentals("AAPL"),
            client.get_fundamentals("AAPL"),
        )
        assert mock_yfin.call_count == 1
        assert all(isinstance(r, FundamentalsData) for r in results)


# ---------------------------------------------------------------------------
# get_ohlcv
# ---------------------------------------------------------------------------


class TestGetOhlcv:
    async def test_returns_dataframe(self, mocker, mock_ohlcv):
        _patch_ticker(mocker, history_df=mock_ohlcv)
        client = MarketClient()
        result = await client.get_ohlcv("AAPL")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    async def test_default_period_is_6mo(self, mocker, mock_ohlcv):
        mock_ticker_inst = mocker.MagicMock()
        mock_ticker_inst.history.return_value = mock_ohlcv
        mocker.patch("yfinance.Ticker", return_value=mock_ticker_inst)
        client = MarketClient()
        await client.get_ohlcv("AAPL")
        mock_ticker_inst.history.assert_called_once_with(period="6mo")

    async def test_returns_data_error_on_exception(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=RuntimeError("timeout"))
        client = MarketClient()
        result = await client.get_ohlcv("AAPL")
        assert isinstance(result, DataError)
        assert result.source == "yfinance"

    async def test_returns_data_error_when_history_raises(self, mocker):
        ticker_inst = mocker.MagicMock()
        ticker_inst.history.side_effect = RuntimeError("rate limited")
        mocker.patch("yfinance.Ticker", return_value=ticker_inst)
        client = MarketClient()
        result = await client.get_ohlcv("AAPL")
        assert isinstance(result, DataError)

    async def test_never_raises(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=Exception("boom"))
        client = MarketClient()
        result = await client.get_ohlcv("AAPL")
        assert isinstance(result, DataError)

    async def test_empty_dataframe_returns_data_error(self, mocker):
        _patch_ticker(mocker, history_df=pd.DataFrame())
        client = MarketClient()
        result = await client.get_ohlcv("INVALID")
        assert isinstance(result, DataError)
        assert result.source == "yfinance"

    async def test_cache_hit_skips_second_yfinance_call(self, mocker, mock_ohlcv):
        mock_yfin = _patch_ticker(mocker, history_df=mock_ohlcv)
        client = MarketClient()
        await client.get_ohlcv("AAPL", period="6mo")
        await client.get_ohlcv("AAPL", period="6mo")
        assert mock_yfin.call_count == 1

    async def test_different_periods_have_separate_cache_entries(self, mocker, mock_ohlcv):
        mock_yfin = _patch_ticker(mocker, history_df=mock_ohlcv)
        client = MarketClient()
        await client.get_ohlcv("AAPL", period="1mo")
        await client.get_ohlcv("AAPL", period="6mo")
        assert mock_yfin.call_count == 2

    async def test_concurrent_same_ticker_hits_yfinance_once(self, mocker, mock_ohlcv):
        mock_yfin = _patch_ticker(mocker, history_df=mock_ohlcv)
        client = MarketClient()
        results = await asyncio.gather(
            client.get_ohlcv("AAPL"),
            client.get_ohlcv("AAPL"),
        )
        assert mock_yfin.call_count == 1
        assert all(isinstance(r, pd.DataFrame) for r in results)


# ---------------------------------------------------------------------------
# get_news
# ---------------------------------------------------------------------------


class TestGetNews:
    async def test_returns_news_items(self, mocker, mock_news_raw):
        _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert isinstance(result, list)
        assert all(isinstance(item, NewsItem) for item in result)

    async def test_news_fields_populated(self, mocker, mock_news_raw):
        _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        result = await client.get_news("AAPL")
        first = result[0]
        assert first.title == "Apple reports strong Q1"
        assert first.publisher == "Reuters"
        assert first.link == "https://reuters.com/article1"
        assert first.published_at.year == 2024

    async def test_limit_slices_results(self, mocker, mock_news_raw):
        _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        result = await client.get_news("AAPL", limit=2)
        assert len(result) == 2

    async def test_default_limit_is_10(self, mocker):
        raw = [
            {
                "id": f"uuid-{i}",
                "content": {
                    "title": f"Headline {i}",
                    "pubDate": "2024-01-01T00:00:00Z",
                    "provider": {"displayName": "Reuters"},
                    "canonicalUrl": {"url": f"https://reuters.com/{i}"},
                },
            }
            for i in range(15)
        ]
        _patch_ticker(mocker, news=raw)
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert len(result) == 10

    async def test_second_call_larger_limit_uses_full_cached_list(self, mocker, mock_news_raw):
        """Cache stores the full fetched list; a larger limit on second call gets full slice."""
        mock_yfin = _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        await client.get_news("AAPL", limit=1)
        result = await client.get_news("AAPL", limit=3)
        assert mock_yfin.call_count == 1
        assert len(result) == 3

    async def test_returns_data_error_on_exception(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=RuntimeError("rate limited"))
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert isinstance(result, DataError)
        assert result.source == "yfinance"

    async def test_returns_data_error_when_news_attr_raises(self, mocker):
        ticker_inst = mocker.MagicMock()
        type(ticker_inst).news = mocker.PropertyMock(side_effect=RuntimeError("malformed response"))
        mocker.patch("yfinance.Ticker", return_value=ticker_inst)
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert isinstance(result, DataError)

    async def test_never_raises(self, mocker):
        mocker.patch("yfinance.Ticker", side_effect=Exception("boom"))
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert isinstance(result, DataError)

    async def test_cache_hit_skips_second_yfinance_call(self, mocker, mock_news_raw):
        mock_yfin = _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        await client.get_news("AAPL", limit=10)
        await client.get_news("AAPL", limit=10)
        assert mock_yfin.call_count == 1

    async def test_concurrent_same_ticker_hits_yfinance_once(self, mocker, mock_news_raw):
        mock_yfin = _patch_ticker(mocker, news=mock_news_raw)
        client = MarketClient()
        results = await asyncio.gather(
            client.get_news("AAPL"),
            client.get_news("AAPL"),
        )
        assert mock_yfin.call_count == 1
        assert all(isinstance(r, list) for r in results)

    async def test_malformed_pub_date_falls_back_to_epoch(self, mocker):
        raw = [
            {
                "id": "uuid-1",
                "content": {
                    "title": "Bad date",
                    "pubDate": "not-a-date",
                    "provider": {"displayName": "Reuters"},
                    "canonicalUrl": {"url": "https://reuters.com/1"},
                },
            }
        ]
        _patch_ticker(mocker, news=raw)
        client = MarketClient()
        result = await client.get_news("AAPL")
        assert isinstance(result, list)
        assert result[0].published_at.year == 1970
