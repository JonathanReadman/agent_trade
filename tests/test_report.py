# tests/test_report.py
import tempfile, os, sqlite3
from datetime import datetime, timezone
from src.db import init_db
from report.report import compute_metrics, ReportMetrics

def _populated_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init_db(f.name)
    conn = sqlite3.connect(f.name)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO trades (ticker, action, confidence, signal_price, execution_price,
            position_size_usd, reasoning, timestamp, status)
        VALUES ('AAPL', 'BUY', 0.8, 150.0, 155.0, 10000.0, 'Strong buy signal', ?, 'executed')
    """, (now,))
    conn.execute("""
        INSERT INTO trades (ticker, action, confidence, signal_price, execution_price,
            position_size_usd, reasoning, timestamp, status)
        VALUES ('MSFT', 'BUY', 0.7, 300.0, 295.0, 8000.0, 'Moderate buy', ?, 'executed')
    """, (now,))
    conn.execute("""
        INSERT INTO portfolio_snapshots (date, total_value_usd, cash_usd, open_positions, spy_close)
        VALUES ('2026-06-07', 100500.0, 82000.0, 2, 540.0)
    """)
    conn.commit()
    conn.close()
    return f.name

def test_compute_metrics_returns_report_metrics():
    db = _populated_db()
    try:
        metrics = compute_metrics(db_path=db, starting_capital=100_000.0)
        assert isinstance(metrics, ReportMetrics)
    finally:
        os.unlink(db)

def test_win_rate_calculated_correctly():
    db = _populated_db()
    try:
        metrics = compute_metrics(db_path=db, starting_capital=100_000.0)
        # AAPL: bought 150, exec 155 → gain. MSFT: bought 300, exec 295 → loss.
        assert metrics.win_rate == 0.5
    finally:
        os.unlink(db)

def test_total_trades_count():
    db = _populated_db()
    try:
        metrics = compute_metrics(db_path=db, starting_capital=100_000.0)
        assert metrics.total_trades == 2
    finally:
        os.unlink(db)
