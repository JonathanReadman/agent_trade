import pytest
from unittest.mock import patch, MagicMock
from src.news import get_news, NewsResult

def _mock_newsapi_response(articles):
    return {"status": "ok", "totalResults": len(articles), "articles": articles}

def test_returns_news_result():
    mock_articles = [
        {"title": "Apple hits record high", "description": "AAPL surged today",
         "publishedAt": "2026-06-07T12:00:00Z", "source": {"name": "Reuters"}}
    ]
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response(mock_articles)
        result = get_news("AAPL", api_key="test_key")
    assert isinstance(result, NewsResult)
    assert result.ticker == "AAPL"
    assert len(result.headlines) == 1
    assert result.headlines[0]["title"] == "Apple hits record high"

def test_returns_empty_result_when_no_articles():
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response([])
        result = get_news("XYZ", api_key="test_key")
    assert result.ticker == "XYZ"
    assert result.headlines == []
    assert result.has_news is False

def test_has_news_true_when_articles_present():
    mock_articles = [
        {"title": "Test headline", "description": "desc",
         "publishedAt": "2026-06-07T10:00:00Z", "source": {"name": "AP"}}
    ]
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response(mock_articles)
        result = get_news("AAPL", api_key="test_key")
    assert result.has_news is True

def test_retries_on_failure():
    with patch("src.news.NewsApiClient") as MockClient:
        with patch("src.news.time.sleep"):
            instance = MockClient.return_value
            instance.get_everything.side_effect = [
                Exception("timeout"),
                Exception("timeout"),
                _mock_newsapi_response([])
            ]
            result = get_news("AAPL", api_key="test_key")
    assert instance.get_everything.call_count == 3
    assert result.headlines == []
