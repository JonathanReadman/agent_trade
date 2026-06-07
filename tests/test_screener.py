from unittest.mock import patch
from src.screener import screen_tickers
from src.news import NewsResult


def test_returns_only_tickers_with_news():
    tickers = ["AAPL", "MSFT", "XYZ"]

    def fake_get_news(ticker, api_key):
        if ticker == "XYZ":
            return NewsResult(ticker=ticker, headlines=[])
        return NewsResult(ticker=ticker, headlines=[{"title": f"{ticker} news", "description": "", "publishedAt": "", "source": ""}])

    with patch("src.screener.get_news", side_effect=fake_get_news):
        result = screen_tickers(tickers, api_key="test_key")

    assert "AAPL" in result
    assert "MSFT" in result
    assert "XYZ" not in result


def test_returns_empty_list_when_no_news():
    tickers = ["AAA", "BBB"]

    with patch("src.screener.get_news") as mock_news:
        mock_news.return_value = NewsResult(ticker="AAA", headlines=[])
        result = screen_tickers(tickers, api_key="test_key")

    assert result == []
