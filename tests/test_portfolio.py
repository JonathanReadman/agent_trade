import tempfile
import os
from src.db import init_db
from src.portfolio import get_portfolio, PortfolioState


def _temp_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init_db(f.name)
    return f.name


def test_returns_portfolio_state_on_empty_db():
    db = _temp_db()
    try:
        state = get_portfolio(db_path=db, starting_capital=100_000.0)
        assert isinstance(state, PortfolioState)
        assert state.cash_usd == 100_000.0
        assert state.holdings == {}
        assert state.total_value_usd == 100_000.0
    finally:
        os.unlink(db)


def test_holdings_reflect_executed_buys():
    import sqlite3
    from datetime import datetime, timezone
    db = _temp_db()
    try:
        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT INTO trades (ticker, action, confidence, signal_price,
                execution_price, position_size_usd, reasoning, timestamp, status)
            VALUES ('AAPL', 'BUY', 0.8, 150.0, 151.0, 10000.0, 'test', ?, 'executed')
        """, (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
        conn.close()
        state = get_portfolio(db_path=db, starting_capital=100_000.0)
        assert "AAPL" in state.holdings
        assert state.holdings["AAPL"] == 10_000.0
        assert state.cash_usd == 90_000.0
    finally:
        os.unlink(db)
