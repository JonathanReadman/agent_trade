import tempfile, os, sqlite3
from unittest.mock import patch
import pandas as pd
from datetime import datetime, timezone
from src.db import init_db
from src.backfill import backfill_execution_prices

def _temp_db_with_trade(ticker="AAPL"):
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init_db(f.name)
    conn = sqlite3.connect(f.name)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        INSERT INTO trades (ticker, action, confidence, signal_price, execution_price,
            position_size_usd, reasoning, timestamp, status)
        VALUES (?, 'BUY', 0.8, 150.0, NULL, 10000.0, 'test', ?, 'executed')
    """, (ticker, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    return f.name

def test_backfills_null_execution_prices():
    db = _temp_db_with_trade("AAPL")
    try:
        mock_df = pd.DataFrame({"Open": [152.0]}, index=pd.date_range("2026-06-08", periods=1))
        with patch("src.backfill.yf.download", return_value=mock_df):
            backfill_execution_prices(db_path=db)
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT execution_price FROM trades WHERE ticker='AAPL'").fetchone()
        conn.close()
        assert row[0] == 152.0
    finally:
        os.unlink(db)

def test_skips_already_filled_trades():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init_db(f.name)
    conn = sqlite3.connect(f.name)
    conn.execute("""
        INSERT INTO trades (ticker, action, confidence, signal_price, execution_price,
            position_size_usd, reasoning, timestamp, status)
        VALUES ('AAPL', 'BUY', 0.8, 150.0, 151.0, 10000.0, 'test', ?, 'executed')
    """, (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()
    with patch("src.backfill.yf.download") as mock_dl:
        backfill_execution_prices(db_path=f.name)
        mock_dl.assert_not_called()
    os.unlink(f.name)
