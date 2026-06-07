import os
from dataclasses import dataclass
from src.db import get_connection, DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))


@dataclass
class PortfolioState:
    cash_usd: float
    holdings: dict  # ticker -> position_size_usd
    total_value_usd: float


def get_portfolio(db_path: str = DEFAULT_DB_PATH,
                  starting_capital: float = STARTING_CAPITAL) -> PortfolioState:
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT ticker, action, position_size_usd
        FROM trades
        WHERE status = 'executed' AND action IN ('BUY', 'SELL')
    """).fetchall()
    conn.close()

    holdings: dict = {}
    for row in rows:
        ticker, action, size = row["ticker"], row["action"], row["position_size_usd"]
        if action == "BUY":
            holdings[ticker] = holdings.get(ticker, 0.0) + size
        elif action == "SELL":
            holdings[ticker] = holdings.get(ticker, 0.0) - size
            if holdings[ticker] <= 0:
                del holdings[ticker]

    invested = sum(holdings.values())
    cash = starting_capital - invested
    total = cash + invested

    return PortfolioState(cash_usd=cash, holdings=holdings, total_value_usd=total)
