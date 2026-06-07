import tempfile, os, sqlite3
import pytest
from src.db import init_db
from src.ledger import execute_trade, TradeResult, ValidationError

SP500_SUBSET = ["AAPL", "MSFT", "AMZN", "GOOGL", "JPM"]

def _temp_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init_db(f.name)
    return f.name

def test_valid_buy_is_recorded():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="BUY", confidence=0.75,
            signal_price=150.0, reasoning="Bullish signal",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert isinstance(result, TradeResult)
        assert result.status == "executed"
        assert result.position_size_usd > 0
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT * FROM trades WHERE ticker='AAPL'").fetchone()
        assert row is not None
        conn.close()
    finally:
        os.unlink(db)

def test_confidence_below_threshold_forces_hold():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="BUY", confidence=0.55,
            signal_price=150.0, reasoning="Weak signal",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert result.status == "rejected"
        assert "confidence" in result.rejection_reason.lower()
    finally:
        os.unlink(db)

def test_invalid_action_rejected():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="MAYBE", confidence=0.8,
            signal_price=150.0, reasoning="test",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert result.status == "rejected"
    finally:
        os.unlink(db)

def test_ticker_not_in_universe_rejected():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="DOGE", action="BUY", confidence=0.8,
            signal_price=0.5, reasoning="test",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert result.status == "rejected"
        assert "universe" in result.rejection_reason.lower()
    finally:
        os.unlink(db)

def test_sell_without_position_rejected():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="SELL", confidence=0.8,
            signal_price=150.0, reasoning="test",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert result.status == "rejected"
        assert "position" in result.rejection_reason.lower()
    finally:
        os.unlink(db)

def test_position_capped_at_10_percent():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="BUY", confidence=1.0,
            signal_price=150.0, reasoning="Max confidence",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        assert result.position_size_usd <= 10_000.0
    finally:
        os.unlink(db)

def test_kelly_fraction_correct():
    db = _temp_db()
    try:
        result = execute_trade(
            ticker="AAPL", action="BUY", confidence=0.8,
            signal_price=150.0, reasoning="test",
            db_path=db, sp500_tickers=SP500_SUBSET, starting_capital=100_000.0
        )
        # kelly fraction = 0.8 - 0.5 = 0.3 → 30% of portfolio → 30000, capped at 10000
        assert result.position_size_usd == 10_000.0
    finally:
        os.unlink(db)
