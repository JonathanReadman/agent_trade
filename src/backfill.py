import yfinance as yf
from src.db import get_connection, DEFAULT_DB_PATH


def backfill_execution_prices(db_path: str = DEFAULT_DB_PATH) -> None:
    """Fetch next-day open prices for trades that are missing execution_price."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT id, ticker FROM trades
        WHERE execution_price IS NULL AND status = 'executed' AND action IN ('BUY', 'SELL')
    """).fetchall()
    conn.close()

    if not rows:
        return

    for row in rows:
        trade_id, ticker = row["id"], row["ticker"]
        try:
            df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                continue
            # Handle both Series and scalar returns from squeeze()
            open_series = df["Open"]
            if hasattr(open_series, 'iloc'):
                open_price = float(open_series.iloc[-1])
            else:
                open_price = float(open_series)
            conn = get_connection(db_path)
            conn.execute(
                "UPDATE trades SET execution_price = ? WHERE id = ?",
                (open_price, trade_id)
            )
            conn.commit()
            conn.close()
        except Exception:
            continue
