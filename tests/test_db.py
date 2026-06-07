import sqlite3
import tempfile
import os
from src.db import init_db, get_connection

def test_init_db_creates_trades_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "trades" in tables
        assert "portfolio_snapshots" in tables
        conn.close()
    finally:
        os.unlink(db_path)

def test_trades_table_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(trades)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"id", "ticker", "action", "confidence", "signal_price",
                    "execution_price", "position_size_usd", "reasoning",
                    "timestamp", "status"}
        assert expected == columns
        conn.close()
    finally:
        os.unlink(db_path)

def test_portfolio_snapshots_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(portfolio_snapshots)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"date", "total_value_usd", "cash_usd", "open_positions", "spy_close"}
        assert expected == columns
        conn.close()
    finally:
        os.unlink(db_path)
