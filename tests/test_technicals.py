# tests/test_technicals.py
import pytest
import pandas as pd
from unittest.mock import patch
from src.technicals import get_technicals, TechnicalsResult

def _make_ohlcv():
    dates = pd.date_range("2026-05-01", periods=60, freq="B")
    import numpy as np
    np.random.seed(42)
    close = 150 + np.cumsum(np.random.randn(60))
    df = pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.random.randint(1_000_000, 5_000_000, 60),
    }, index=dates)
    return df

def test_returns_technicals_result():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = _make_ohlcv()
        result = get_technicals("AAPL")
    assert isinstance(result, TechnicalsResult)
    assert result.ticker == "AAPL"

def test_contains_required_fields():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = _make_ohlcv()
        result = get_technicals("AAPL")
    assert result.close_price > 0
    assert result.volume > 0
    assert result.rsi is not None
    assert result.macd is not None
    assert result.macd_signal is not None

def test_returns_none_result_on_empty_data():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = pd.DataFrame()
        result = get_technicals("BADTICKER")
    assert result is None
