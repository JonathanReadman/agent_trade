import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trading.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence REAL NOT NULL,
            signal_price REAL,
            execution_price REAL,
            position_size_usd REAL,
            reasoning TEXT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'executed'
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            date TEXT PRIMARY KEY,
            total_value_usd REAL NOT NULL,
            cash_usd REAL NOT NULL,
            open_positions INTEGER NOT NULL,
            spy_close REAL
        );
    """)
    conn.commit()
    conn.close()
