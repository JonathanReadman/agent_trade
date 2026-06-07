from src.universe import get_sp500_tickers


def test_returns_list_of_strings():
    tickers = get_sp500_tickers()
    assert isinstance(tickers, list)
    assert all(isinstance(t, str) for t in tickers)


def test_reasonable_count():
    tickers = get_sp500_tickers()
    assert 490 <= len(tickers) <= 510


def test_known_tickers_present():
    tickers = get_sp500_tickers()
    for ticker in ["AAPL", "MSFT", "AMZN", "GOOGL", "JPM"]:
        assert ticker in tickers


def test_no_duplicates():
    tickers = get_sp500_tickers()
    assert len(tickers) == len(set(tickers))
