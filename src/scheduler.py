import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import schedule
import time

from src.db import init_db, get_connection, DEFAULT_DB_PATH
from src.universe import get_sp500_tickers
from src.screener import screen_tickers
from src.agent import run_agent_cycle
from src.backfill import backfill_execution_prices

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NEWS_API_KEY = os.environ["NEWS_API_KEY"]


def is_trading_day(date_str: str) -> bool:
    """Check if a date is a trading day on NYSE.

    Attempts to use pandas_market_calendars, but falls back to
    simple weekday check if library fails (e.g., Python 3.9 compatibility).
    """
    try:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        schedule_df = nyse.schedule(start_date=date_str, end_date=date_str)
        return not schedule_df.empty
    except (TypeError, ImportError):
        # Fallback: simple weekday check (Mon-Fri)
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Monday=0, Sunday=6
        return dt.weekday() < 5


def take_portfolio_snapshot(db_path: str = DEFAULT_DB_PATH) -> None:
    import yfinance as yf
    from src.portfolio import get_portfolio
    state = get_portfolio(db_path=db_path)
    try:
        spy = yf.download("SPY", period="1d", interval="1d", progress=False, auto_adjust=True)
        spy_close = float(spy["Close"].squeeze().iloc[-1]) if not spy.empty else None
    except Exception:
        spy_close = None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO portfolio_snapshots
            (date, total_value_usd, cash_usd, open_positions, spy_close)
        VALUES (?, ?, ?, ?, ?)
    """, (today, state.total_value_usd, state.cash_usd,
          len(state.holdings), spy_close))
    conn.commit()
    conn.close()
    log.info(f"Snapshot: total=${state.total_value_usd:.2f}, cash=${state.cash_usd:.2f}")


def run_daily_cycle() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not is_trading_day(today):
        log.info(f"Not a trading day: {today}. Skipping.")
        return

    log.info(f"Starting daily cycle for {today}")
    init_db()

    # Morning: backfill yesterday's execution prices
    backfill_execution_prices()

    # Screen for tickers with news
    all_tickers = get_sp500_tickers()
    log.info(f"Screening {len(all_tickers)} tickers for news...")
    active_tickers = screen_tickers(all_tickers, api_key=NEWS_API_KEY)
    log.info(f"{len(active_tickers)} tickers have news today: {active_tickers[:10]}...")

    if not active_tickers:
        log.info("No active tickers. Skipping agent cycle.")
        take_portfolio_snapshot()
        return

    # Run agent
    log.info("Running agent cycle...")
    summary = run_agent_cycle(
        tickers=active_tickers,
        api_key=ANTHROPIC_API_KEY,
        news_api_key=NEWS_API_KEY,
    )
    log.info(f"Agent summary: {summary}")

    # Snapshot
    take_portfolio_snapshot()
    log.info("Daily cycle complete.")


if __name__ == "__main__":
    # Run once immediately, then schedule for 4:30pm ET daily
    run_daily_cycle()
    schedule.every().day.at("21:30").do(run_daily_cycle)  # 21:30 UTC = 4:30pm ET
    log.info("Scheduler running. Next cycle at 4:30pm ET.")
    while True:
        schedule.run_pending()
        time.sleep(60)
