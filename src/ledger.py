import os
from dataclasses import dataclass
from datetime import datetime, timezone
from src.db import get_connection, DEFAULT_DB_PATH
from src.portfolio import get_portfolio

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
MIN_CONFIDENCE = 0.6
MAX_POSITION_PCT = 0.10
VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


class ValidationError(Exception):
    pass


@dataclass
class TradeResult:
    status: str           # "executed" | "rejected" | "skipped"
    position_size_usd: float = 0.0
    rejection_reason: str = ""


def execute_trade(
    ticker: str,
    action: str,
    confidence: float,
    signal_price: float,
    reasoning: str,
    db_path: str = DEFAULT_DB_PATH,
    sp500_tickers=None,
    starting_capital: float = STARTING_CAPITAL,
) -> TradeResult:
    from src.universe import get_sp500_tickers
    universe = sp500_tickers if sp500_tickers is not None else get_sp500_tickers()

    def reject(reason: str) -> TradeResult:
        _log_trade(ticker, action, confidence, signal_price, 0.0, reasoning,
                   "rejected", db_path)
        return TradeResult(status="rejected", rejection_reason=reason)

    if action not in VALID_ACTIONS:
        return reject(f"invalid action: {action}")

    if ticker not in universe:
        return reject(f"ticker not in s&p 500 universe: {ticker}")

    if action == "HOLD":
        return TradeResult(status="skipped")

    if confidence < MIN_CONFIDENCE:
        return reject(f"confidence {confidence:.2f} below minimum {MIN_CONFIDENCE}")

    if not (0.0 <= confidence <= 1.0):
        return reject(f"confidence {confidence} outside [0, 1]")

    portfolio = get_portfolio(db_path=db_path, starting_capital=starting_capital)

    if action == "SELL":
        if ticker not in portfolio.holdings:
            return reject(f"no existing position to sell: {ticker}")

    kelly_fraction = confidence - 0.5
    max_position = portfolio.total_value_usd * MAX_POSITION_PCT
    position_size = min(kelly_fraction * portfolio.total_value_usd, max_position)
    position_size = round(position_size, 2)

    _log_trade(ticker, action, confidence, signal_price, position_size, reasoning,
               "executed", db_path)

    return TradeResult(status="executed", position_size_usd=position_size)


def _log_trade(ticker, action, confidence, signal_price, position_size,
               reasoning, status, db_path):
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO trades
            (ticker, action, confidence, signal_price, position_size_usd,
             reasoning, timestamp, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, action, confidence, signal_price, position_size,
          reasoning, datetime.now(timezone.utc).isoformat(), status))
    conn.commit()
    conn.close()
