from src.news import get_news, NewsResult


def screen_tickers(tickers: list, api_key: str) -> list:
    """Returns tickers that have at least one news article in the last 24 hours."""
    active = []
    for ticker in tickers:
        result = get_news(ticker, api_key=api_key)
        if result.has_news:
            active.append(ticker)
    return active
