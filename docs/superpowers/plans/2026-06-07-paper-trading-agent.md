# Paper Trading Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-of-day Claude-powered paper trading agent that reasons over S&P 500 news sentiment and technical signals, records trades in SQLite, and generates an HTML evaluation report.

**Architecture:** A single Claude agent is given four Python tools (get_news, get_technicals, get_portfolio, execute_trade) and a list of news-screened S&P 500 tickers. It reasons through each ticker sequentially, logs its chain-of-thought, and writes BUY/SELL/HOLD decisions to SQLite. A separate report script reads the ledger and produces a self-contained HTML evaluation.

**Tech Stack:** Python 3.11+, `anthropic`, `yfinance`, `pandas_ta`, `newsapi-python`, `pandas_market_calendars`, `jinja2`, `schedule`, `sqlite3` (stdlib), Chart.js (CDN).

---

## File Structure

```
agent_trade/
├── src/
│   ├── db.py              # SQLite schema creation and connection helper
│   ├── universe.py        # S&P 500 ticker list loader
│   ├── news.py            # get_news() tool — NewsAPI fetch with retry
│   ├── technicals.py      # get_technicals() tool — yfinance + pandas_ta
│   ├── portfolio.py       # get_portfolio() tool — reads SQLite holdings
│   ├── ledger.py          # execute_trade() tool — validates + writes trades
│   ├── screener.py        # news volume pre-screen, returns active tickers
│   ├── agent.py           # Claude API call, tool dispatch loop, cycle runner
│   ├── backfill.py        # next-day open price backfill job
│   └── scheduler.py       # daily schedule entry point
├── report/
│   ├── report.py          # reads SQLite, computes metrics, renders HTML
│   └── template.html      # jinja2 HTML template with Chart.js
├── tests/
│   ├── test_db.py
│   ├── test_universe.py
│   ├── test_news.py
│   ├── test_technicals.py
│   ├── test_portfolio.py
│   ├── test_ledger.py
│   ├── test_screener.py
│   ├── test_agent.py
│   ├── test_backfill.py
│   └── test_report.py
├── .env.example           # ANTHROPIC_API_KEY, NEWS_API_KEY
├── requirements.txt
└── README.md
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Create requirements.txt**

```
anthropic>=0.25.0
yfinance>=0.2.38
pandas_ta>=0.3.14b
newsapi-python>=0.2.7
pandas_market_calendars>=4.3.1
jinja2>=3.1.4
schedule>=1.2.1
python-dotenv>=1.0.1
pytest>=8.2.0
pytest-mock>=3.14.0
```

- [ ] **Step 2: Create .env.example**

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
NEWS_API_KEY=your_newsapi_key_here
STARTING_CAPITAL=100000
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Create README.md**

```markdown
# Agent Trade — Paper Trading Agent

A Claude-powered paper trading agent for S&P 500 stocks.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys
2. `pip install -r requirements.txt`
3. `python src/scheduler.py` — runs the daily cycle (or waits for market close)
4. `python report/report.py` — generates `report.html` in the project root

## Environment Variables

- `ANTHROPIC_API_KEY` — from console.anthropic.com
- `NEWS_API_KEY` — from newsapi.org (free tier)
- `STARTING_CAPITAL` — paper portfolio starting value in USD (default: 100000)
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example README.md
git commit -m "feat: project setup and dependencies"
```

---

## Task 2: Database Schema

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.db'`

- [ ] **Step 3: Implement src/db.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: sqlite schema — trades and portfolio_snapshots tables"
```

---

## Task 3: S&P 500 Universe

**Files:**
- Create: `src/universe.py`
- Create: `tests/test_universe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_universe.py
from src.universe import get_sp500_tickers

def test_returns_list_of_strings():
    tickers = get_sp500_tickers()
    assert isinstance(tickers, list)
    assert all(isinstance(t, str) for t in tickers)

def test_reasonable_count():
    tickers = get_sp500_tickers()
    assert 490 <= len(tickers) <= 510

def test_known_tickers_present():
    tickers = get_sp500_tickers()
    for ticker in ["AAPL", "MSFT", "AMZN", "GOOGL", "JPM"]:
        assert ticker in tickers

def test_no_duplicates():
    tickers = get_sp500_tickers()
    assert len(tickers) == len(set(tickers))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_universe.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/universe.py**

```python
import pandas as pd
from functools import lru_cache

@lru_cache(maxsize=1)
def get_sp500_tickers() -> list[str]:
    """Fetches current S&P 500 constituents from Wikipedia."""
    tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = tables[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return tickers
```

- [ ] **Step 4: Run tests (requires internet)**

```bash
pytest tests/test_universe.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/universe.py tests/test_universe.py
git commit -m "feat: s&p 500 universe loader from wikipedia"
```

---

## Task 4: News Tool

**Files:**
- Create: `src/news.py`
- Create: `tests/test_news.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_news.py
import pytest
from unittest.mock import patch, MagicMock
from src.news import get_news, NewsResult

def _mock_newsapi_response(articles):
    return {"status": "ok", "totalResults": len(articles), "articles": articles}

def test_returns_news_result():
    mock_articles = [
        {"title": "Apple hits record high", "description": "AAPL surged today",
         "publishedAt": "2026-06-07T12:00:00Z", "source": {"name": "Reuters"}}
    ]
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response(mock_articles)
        result = get_news("AAPL", api_key="test_key")
    assert isinstance(result, NewsResult)
    assert result.ticker == "AAPL"
    assert len(result.headlines) == 1
    assert result.headlines[0]["title"] == "Apple hits record high"

def test_returns_empty_result_when_no_articles():
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response([])
        result = get_news("XYZ", api_key="test_key")
    assert result.ticker == "XYZ"
    assert result.headlines == []
    assert result.has_news is False

def test_has_news_true_when_articles_present():
    mock_articles = [
        {"title": "Test headline", "description": "desc",
         "publishedAt": "2026-06-07T10:00:00Z", "source": {"name": "AP"}}
    ]
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.return_value = _mock_newsapi_response(mock_articles)
        result = get_news("AAPL", api_key="test_key")
    assert result.has_news is True

def test_retries_on_failure():
    with patch("src.news.NewsApiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_everything.side_effect = [
            Exception("timeout"),
            Exception("timeout"),
            _mock_newsapi_response([])
        ]
        result = get_news("AAPL", api_key="test_key")
    assert instance.get_everything.call_count == 3
    assert result.headlines == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_news.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/news.py**

```python
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from newsapi import NewsApiClient


@dataclass
class NewsResult:
    ticker: str
    headlines: list[dict]

    @property
    def has_news(self) -> bool:
        return len(self.headlines) > 0


def get_news(ticker: str, api_key: str, max_retries: int = 3) -> NewsResult:
    client = NewsApiClient(api_key=api_key)
    from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.get_everything(
                q=ticker,
                from_param=from_date,
                language="en",
                sort_by="relevancy",
                page_size=5,
            )
            articles = response.get("articles", [])
            headlines = [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "publishedAt": a.get("publishedAt", ""),
                    "source": a.get("source", {}).get("name", ""),
                }
                for a in articles
            ]
            return NewsResult(ticker=ticker, headlines=headlines)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return NewsResult(ticker=ticker, headlines=[])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_news.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/news.py tests/test_news.py
git commit -m "feat: news tool with newsapi fetch and retry"
```

---

## Task 5: Technicals Tool

**Files:**
- Create: `src/technicals.py`
- Create: `tests/test_technicals.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_technicals.py
import pytest
import pandas as pd
from unittest.mock import patch
from src.technicals import get_technicals, TechnicalsResult

def _make_ohlcv():
    dates = pd.date_range("2026-05-01", periods=60, freq="B")
    import numpy as np
    np.random.seed(42)
    close = 150 + np.cumsum(np.random.randn(60))
    df = pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.random.randint(1_000_000, 5_000_000, 60),
    }, index=dates)
    return df

def test_returns_technicals_result():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = _make_ohlcv()
        result = get_technicals("AAPL")
    assert isinstance(result, TechnicalsResult)
    assert result.ticker == "AAPL"

def test_contains_required_fields():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = _make_ohlcv()
        result = get_technicals("AAPL")
    assert result.close_price > 0
    assert result.volume > 0
    assert result.rsi is not None
    assert result.macd is not None
    assert result.macd_signal is not None

def test_returns_none_result_on_empty_data():
    with patch("src.technicals.yf.download") as mock_dl:
        mock_dl.return_value = pd.DataFrame()
        result = get_technicals("BADTICKER")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_technicals.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/technicals.py**

```python
import time
from dataclasses import dataclass
import yfinance as yf
import pandas_ta as ta
import pandas as pd


@dataclass
class TechnicalsResult:
    ticker: str
    close_price: float
    volume: int
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    price_change_pct: float | None


def get_technicals(ticker: str, max_retries: int = 3) -> TechnicalsResult | None:
    last_error = None
    for attempt in range(max_retries):
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return None

            close = df["Close"]
            rsi_series = ta.rsi(close, length=14)
            macd_df = ta.macd(close, fast=12, slow=26, signal=9)

            latest_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2]) if len(close) > 1 else latest_close
            price_change_pct = (latest_close - prev_close) / prev_close * 100

            rsi_val = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else None
            macd_val = None
            macd_signal_val = None
            if macd_df is not None and not macd_df.empty:
                macd_col = [c for c in macd_df.columns if c.startswith("MACD_") and "s" not in c.lower() and "h" not in c.lower()]
                sig_col = [c for c in macd_df.columns if "MACDs_" in c]
                if macd_col:
                    macd_val = float(macd_df[macd_col[0]].iloc[-1])
                if sig_col:
                    macd_signal_val = float(macd_df[sig_col[0]].iloc[-1])

            return TechnicalsResult(
                ticker=ticker,
                close_price=latest_close,
                volume=int(df["Volume"].iloc[-1]),
                rsi=rsi_val,
                macd=macd_val,
                macd_signal=macd_signal_val,
                price_change_pct=price_change_pct,
            )
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_technicals.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/technicals.py tests/test_technicals.py
git commit -m "feat: technicals tool with rsi and macd via yfinance and pandas_ta"
```

---

## Task 6: Portfolio Tool

**Files:**
- Create: `src/portfolio.py`
- Create: `tests/test_portfolio.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_portfolio.py
import tempfile, os
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_portfolio.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/portfolio.py**

```python
import os
from dataclasses import dataclass, field
from src.db import get_connection, DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))


@dataclass
class PortfolioState:
    cash_usd: float
    holdings: dict[str, float]  # ticker -> position_size_usd
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

    holdings: dict[str, float] = {}
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_portfolio.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/portfolio.py tests/test_portfolio.py
git commit -m "feat: portfolio tool reads holdings from trade ledger"
```

---

## Task 7: Ledger (execute_trade)

**Files:**
- Create: `src/ledger.py`
- Create: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ledger.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ledger.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/ledger.py**

```python
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
    sp500_tickers: list[str] | None = None,
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ledger.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ledger.py tests/test_ledger.py
git commit -m "feat: execute_trade ledger with kelly sizing and validation"
```

---

## Task 8: News Pre-Screener

**Files:**
- Create: `src/screener.py`
- Create: `tests/test_screener.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_screener.py
from unittest.mock import patch
from src.screener import screen_tickers
from src.news import NewsResult

def test_returns_only_tickers_with_news():
    tickers = ["AAPL", "MSFT", "XYZ"]

    def fake_get_news(ticker, api_key):
        if ticker == "XYZ":
            return NewsResult(ticker=ticker, headlines=[])
        return NewsResult(ticker=ticker, headlines=[{"title": f"{ticker} news", "description": "", "publishedAt": "", "source": ""}])

    with patch("src.screener.get_news", side_effect=fake_get_news):
        result = screen_tickers(tickers, api_key="test_key")

    assert "AAPL" in result
    assert "MSFT" in result
    assert "XYZ" not in result

def test_returns_empty_list_when_no_news():
    tickers = ["AAA", "BBB"]

    with patch("src.screener.get_news") as mock_news:
        mock_news.return_value = NewsResult(ticker="AAA", headlines=[])
        result = screen_tickers(tickers, api_key="test_key")

    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_screener.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/screener.py**

```python
from src.news import get_news, NewsResult


def screen_tickers(tickers: list[str], api_key: str) -> list[str]:
    """Returns tickers that have at least one news article in the last 24 hours."""
    active = []
    for ticker in tickers:
        result = get_news(ticker, api_key=api_key)
        if result.has_news:
            active.append(ticker)
    return active
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_screener.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/screener.py tests/test_screener.py
git commit -m "feat: news pre-screener filters tickers with no recent coverage"
```

---

## Task 9: Claude Agent

**Files:**
- Create: `src/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from src.agent import build_tool_definitions, run_agent_cycle

def test_build_tool_definitions_returns_four_tools():
    tools = build_tool_definitions()
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_news", "get_technicals", "get_portfolio", "execute_trade"}

def test_each_tool_has_required_fields():
    tools = build_tool_definitions()
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool

def test_run_agent_cycle_returns_summary(monkeypatch):
    mock_client = MagicMock()
    # Simulate Claude returning a final text message (no tool calls)
    mock_message = MagicMock()
    mock_message.stop_reason = "end_turn"
    mock_message.content = [MagicMock(type="text", text="Analysis complete. No strong signals today.")]
    mock_client.messages.create.return_value = mock_message

    with patch("src.agent.anthropic.Anthropic", return_value=mock_client):
        summary = run_agent_cycle(
            tickers=["AAPL"],
            api_key="test_key",
            news_api_key="test_news_key",
            db_path=":memory:",
        )

    assert isinstance(summary, str)
    assert len(summary) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/agent.py**

```python
import json
import os
import anthropic
from src.news import get_news
from src.technicals import get_technicals
from src.portfolio import get_portfolio
from src.ledger import execute_trade
from src.universe import get_sp500_tickers
from src.db import DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
MODEL = "claude-opus-4-8"


def build_tool_definitions() -> list[dict]:
    return [
        {
            "name": "get_news",
            "description": "Fetch recent news headlines for a stock ticker from the last 24 hours.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_technicals",
            "description": "Fetch technical indicators for a stock: close price, volume, RSI, MACD, and 1-day price change %.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_portfolio",
            "description": "Get current paper portfolio state: cash balance, open holdings, total value.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "execute_trade",
            "description": (
                "Record a paper trade decision. Action must be BUY, SELL, or HOLD. "
                "Confidence is 0.0–1.0. Trades below 0.6 confidence are rejected. "
                "Position size is calculated automatically via Kelly criterion."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "signal_price": {"type": "number", "description": "Current price at time of decision"},
                    "reasoning": {"type": "string", "description": "Your full chain-of-thought reasoning for this decision"},
                },
                "required": ["ticker", "action", "confidence", "signal_price", "reasoning"],
            },
        },
    ]


def _dispatch_tool(tool_name: str, tool_input: dict, news_api_key: str,
                   db_path: str) -> str:
    if tool_name == "get_news":
        result = get_news(tool_input["ticker"], api_key=news_api_key)
        return json.dumps({"ticker": result.ticker, "headlines": result.headlines})

    if tool_name == "get_technicals":
        result = get_technicals(tool_input["ticker"])
        if result is None:
            return json.dumps({"error": "no data available"})
        return json.dumps({
            "ticker": result.ticker,
            "close_price": result.close_price,
            "volume": result.volume,
            "rsi": result.rsi,
            "macd": result.macd,
            "macd_signal": result.macd_signal,
            "price_change_pct": result.price_change_pct,
        })

    if tool_name == "get_portfolio":
        state = get_portfolio(db_path=db_path)
        return json.dumps({
            "cash_usd": state.cash_usd,
            "total_value_usd": state.total_value_usd,
            "holdings": state.holdings,
        })

    if tool_name == "execute_trade":
        result = execute_trade(
            ticker=tool_input["ticker"],
            action=tool_input["action"],
            confidence=tool_input["confidence"],
            signal_price=tool_input["signal_price"],
            reasoning=tool_input["reasoning"],
            db_path=db_path,
        )
        return json.dumps({
            "status": result.status,
            "position_size_usd": result.position_size_usd,
            "rejection_reason": result.rejection_reason,
        })

    return json.dumps({"error": f"unknown tool: {tool_name}"})


def run_agent_cycle(
    tickers: list[str],
    api_key: str,
    news_api_key: str,
    db_path: str = DEFAULT_DB_PATH,
) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    tools = build_tool_definitions()

    system_prompt = (
        "You are a disciplined paper trading agent. You analyze S&P 500 stocks using "
        "news sentiment and technical indicators, then make BUY, SELL, or HOLD decisions. "
        "For each ticker: (1) fetch news, (2) fetch technicals, (3) check portfolio, "
        "(4) reason carefully, (5) call execute_trade with your decision and a detailed reasoning string. "
        "Be conservative. Only trade with high conviction. Your reasoning text is logged for audit — "
        "explain your thinking clearly. Do not trade on weak or ambiguous signals."
    )

    user_message = (
        f"Please analyze the following S&P 500 tickers and make paper trading decisions for each: "
        f"{', '.join(tickers)}. "
        f"Work through each ticker systematically using your tools."
    )

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return " ".join(text_blocks) if text_blocks else "Cycle complete."

        if response.stop_reason != "tool_use":
            return f"Unexpected stop reason: {response.stop_reason}"

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_content = _dispatch_tool(
                    block.name, block.input, news_api_key, db_path
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_content,
                })

        messages.append({"role": "user", "content": tool_results})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent.py tests/test_agent.py
git commit -m "feat: claude agent with tool dispatch loop"
```

---

## Task 10: Execution Price Backfill

**Files:**
- Create: `src/backfill.py`
- Create: `tests/test_backfill.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backfill.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_backfill.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement src/backfill.py**

```python
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
            open_price = float(df["Open"].iloc[-1])
            conn = get_connection(db_path)
            conn.execute(
                "UPDATE trades SET execution_price = ? WHERE id = ?",
                (open_price, trade_id)
            )
            conn.commit()
            conn.close()
        except Exception:
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_backfill.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backfill.py tests/test_backfill.py
git commit -m "feat: backfill execution prices from next-day open"
```

---

## Task 11: Scheduler Entry Point

**Files:**
- Create: `src/scheduler.py`

- [ ] **Step 1: Implement src/scheduler.py**

```python
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas_market_calendars as mcal
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
    nyse = mcal.get_calendar("NYSE")
    schedule_df = nyse.schedule(start_date=date_str, end_date=date_str)
    return not schedule_df.empty


def take_portfolio_snapshot(db_path: str = DEFAULT_DB_PATH) -> None:
    import yfinance as yf
    from src.portfolio import get_portfolio
    state = get_portfolio(db_path=db_path)
    try:
        spy = yf.download("SPY", period="1d", interval="1d", progress=False, auto_adjust=True)
        spy_close = float(spy["Close"].iloc[-1]) if not spy.empty else None
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
```

- [ ] **Step 2: Test manually (dry run with no API keys)**

```bash
cd /path/to/agent_trade
python -c "from src.scheduler import is_trading_day; print(is_trading_day('2026-06-09'))"
```

Expected: prints `True` or `False` without error.

- [ ] **Step 3: Commit**

```bash
git add src/scheduler.py
git commit -m "feat: daily scheduler with market calendar check and portfolio snapshot"
```

---

## Task 12: HTML Report

**Files:**
- Create: `report/report.py`
- Create: `report/template.html`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_report.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement report/report.py**

```python
import os
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.db import DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))


@dataclass
class TradeRecord:
    ticker: str
    action: str
    confidence: float
    signal_price: float
    execution_price: float
    position_size_usd: float
    reasoning: str
    timestamp: str
    pnl_pct: float = 0.0


@dataclass
class ReportMetrics:
    total_trades: int
    win_rate: float
    avg_gain_pct: float
    avg_loss_pct: float
    sharpe_ratio: float | None
    portfolio_pnl_pct: float
    spy_pnl_pct: float
    trades: list[TradeRecord]
    snapshots: list[dict]


def compute_metrics(db_path: str = DEFAULT_DB_PATH,
                    starting_capital: float = STARTING_CAPITAL) -> ReportMetrics:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    trade_rows = conn.execute("""
        SELECT ticker, action, confidence, signal_price, execution_price,
               position_size_usd, reasoning, timestamp
        FROM trades
        WHERE status = 'executed' AND action IN ('BUY', 'SELL')
              AND execution_price IS NOT NULL AND signal_price IS NOT NULL
    """).fetchall()

    snapshot_rows = conn.execute("""
        SELECT date, total_value_usd, cash_usd, spy_close
        FROM portfolio_snapshots ORDER BY date
    """).fetchall()
    conn.close()

    trades = []
    gains, losses = [], []
    for row in trade_rows:
        pnl_pct = ((row["execution_price"] - row["signal_price"]) / row["signal_price"] * 100
                   if row["action"] == "BUY" else
                   (row["signal_price"] - row["execution_price"]) / row["signal_price"] * 100)
        t = TradeRecord(
            ticker=row["ticker"], action=row["action"],
            confidence=row["confidence"], signal_price=row["signal_price"],
            execution_price=row["execution_price"],
            position_size_usd=row["position_size_usd"],
            reasoning=row["reasoning"], timestamp=row["timestamp"],
            pnl_pct=round(pnl_pct, 4),
        )
        trades.append(t)
        if pnl_pct > 0:
            gains.append(pnl_pct)
        else:
            losses.append(pnl_pct)

    total = len(trades)
    win_rate = len(gains) / total if total > 0 else 0.0
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    snapshots = [dict(s) for s in snapshot_rows]
    portfolio_pnl_pct = 0.0
    spy_pnl_pct = 0.0
    sharpe = None
    if snapshots:
        latest = snapshots[-1]
        portfolio_pnl_pct = (latest["total_value_usd"] - starting_capital) / starting_capital * 100
        first_spy = snapshots[0].get("spy_close")
        last_spy = latest.get("spy_close")
        if first_spy and last_spy and first_spy > 0:
            spy_pnl_pct = (last_spy - first_spy) / first_spy * 100

        if len(snapshots) > 1:
            daily_returns = []
            for i in range(1, len(snapshots)):
                prev = snapshots[i - 1]["total_value_usd"]
                curr = snapshots[i]["total_value_usd"]
                if prev > 0:
                    daily_returns.append((curr - prev) / prev)
            if daily_returns:
                import statistics
                mean_r = statistics.mean(daily_returns)
                std_r = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
                sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else None

    return ReportMetrics(
        total_trades=total,
        win_rate=round(win_rate, 4),
        avg_gain_pct=round(avg_gain, 4),
        avg_loss_pct=round(avg_loss, 4),
        sharpe_ratio=round(sharpe, 3) if sharpe is not None else None,
        portfolio_pnl_pct=round(portfolio_pnl_pct, 4),
        spy_pnl_pct=round(spy_pnl_pct, 4),
        trades=sorted(trades, key=lambda t: t.pnl_pct, reverse=True),
        snapshots=snapshots,
    )


def generate_report(output_path: str = "report.html",
                    db_path: str = DEFAULT_DB_PATH) -> None:
    metrics = compute_metrics(db_path=db_path)
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template.html")
    html = template.render(
        metrics=metrics,
        snapshots_json=json.dumps(metrics.snapshots),
        trades_json=json.dumps([
            {"ticker": t.ticker, "confidence": t.confidence, "pnl_pct": t.pnl_pct}
            for t in metrics.trades
        ]),
    )
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    generate_report()
```

- [ ] **Step 4: Create report/template.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Trade Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d0d0f; color: #e8e6e0; margin: 0; padding: 2rem; }
  h1 { font-size: 2rem; margin-bottom: 0.5rem; }
  .subtitle { color: #888; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1a1a1f; border-radius: 8px; padding: 1.25rem; }
  .card .label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.75rem; font-weight: 700; margin-top: 0.25rem; }
  .positive { color: #3ab87a; }
  .negative { color: #e85d3a; }
  .neutral { color: #e8e6e0; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }
  .chart-box { background: #1a1a1f; border-radius: 8px; padding: 1.25rem; }
  .chart-box h3 { margin: 0 0 1rem; font-size: 0.9rem; color: #bbb; }
  table { width: 100%; border-collapse: collapse; background: #1a1a1f; border-radius: 8px; overflow: hidden; }
  th { background: #111; padding: 0.75rem 1rem; text-align: left; font-size: 0.75rem; text-transform: uppercase; color: #888; }
  td { padding: 0.75rem 1rem; border-top: 1px solid #222; font-size: 0.875rem; }
  .reasoning { font-size: 0.75rem; color: #888; max-width: 400px; }
  @media (max-width: 768px) { .charts { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>Agent Trade</h1>
<p class="subtitle">Paper Trading Report — S&amp;P 500 · Claude Opus</p>

<div class="grid">
  <div class="card">
    <div class="label">Portfolio P&amp;L</div>
    <div class="value {% if metrics.portfolio_pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
      {{ "%.2f"|format(metrics.portfolio_pnl_pct) }}%
    </div>
  </div>
  <div class="card">
    <div class="label">SPY Benchmark</div>
    <div class="value {% if metrics.spy_pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
      {{ "%.2f"|format(metrics.spy_pnl_pct) }}%
    </div>
  </div>
  <div class="card">
    <div class="label">Win Rate</div>
    <div class="value neutral">{{ "%.0f"|format(metrics.win_rate * 100) }}%</div>
  </div>
  <div class="card">
    <div class="label">Total Trades</div>
    <div class="value neutral">{{ metrics.total_trades }}</div>
  </div>
  <div class="card">
    <div class="label">Avg Gain</div>
    <div class="value positive">{{ "%.2f"|format(metrics.avg_gain_pct) }}%</div>
  </div>
  <div class="card">
    <div class="label">Avg Loss</div>
    <div class="value negative">{{ "%.2f"|format(metrics.avg_loss_pct) }}%</div>
  </div>
  {% if metrics.sharpe_ratio is not none %}
  <div class="card">
    <div class="label">Sharpe Ratio</div>
    <div class="value neutral">{{ "%.2f"|format(metrics.sharpe_ratio) }}</div>
  </div>
  {% endif %}
</div>

<div class="charts">
  <div class="chart-box">
    <h3>Portfolio vs SPY (Daily)</h3>
    <canvas id="portfolioChart" height="200"></canvas>
  </div>
  <div class="chart-box">
    <h3>Confidence Calibration</h3>
    <canvas id="calibrationChart" height="200"></canvas>
  </div>
</div>

<h2 style="margin-bottom:1rem">All Trades</h2>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Action</th><th>Confidence</th>
      <th>Signal Price</th><th>Exec Price</th><th>P&amp;L %</th><th>Reasoning</th>
    </tr>
  </thead>
  <tbody>
    {% for trade in metrics.trades %}
    <tr>
      <td><strong>{{ trade.ticker }}</strong></td>
      <td>{{ trade.action }}</td>
      <td>{{ "%.0f"|format(trade.confidence * 100) }}%</td>
      <td>${{ "%.2f"|format(trade.signal_price) }}</td>
      <td>{% if trade.execution_price %}${{ "%.2f"|format(trade.execution_price) }}{% else %}—{% endif %}</td>
      <td class="{% if trade.pnl_pct > 0 %}positive{% elif trade.pnl_pct < 0 %}negative{% else %}neutral{% endif %}">
        {{ "%.2f"|format(trade.pnl_pct) }}%
      </td>
      <td class="reasoning">{{ trade.reasoning[:200] }}{% if trade.reasoning|length > 200 %}…{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<script>
const snapshots = {{ snapshots_json }};
const tradesData = {{ trades_json }};

if (snapshots.length > 1) {
  new Chart(document.getElementById('portfolioChart'), {
    type: 'line',
    data: {
      labels: snapshots.map(s => s.date),
      datasets: [
        { label: 'Portfolio', data: snapshots.map(s => s.total_value_usd), borderColor: '#3ab87a', tension: 0.3, fill: false },
        { label: 'SPY (scaled)', data: snapshots.map(s => s.spy_close ? s.spy_close * (100000 / snapshots[0].spy_close) : null), borderColor: '#3a7be8', tension: 0.3, fill: false, borderDash: [5,5] }
      ]
    },
    options: { responsive: true, plugins: { legend: { labels: { color: '#e8e6e0' } } }, scales: { x: { ticks: { color: '#888' } }, y: { ticks: { color: '#888' } } } }
  });
}

if (tradesData.length > 0) {
  new Chart(document.getElementById('calibrationChart'), {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Trade',
        data: tradesData.map(t => ({ x: t.confidence, y: t.pnl_pct })),
        backgroundColor: tradesData.map(t => t.pnl_pct >= 0 ? 'rgba(58,184,122,0.7)' : 'rgba(232,93,58,0.7)'),
        pointRadius: 6,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Confidence', color: '#888' }, ticks: { color: '#888' }, min: 0.5, max: 1.0 },
        y: { title: { display: true, text: 'P&L %', color: '#888' }, ticks: { color: '#888' } }
      }
    }
  });
}
</script>
</body>
</html>
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_report.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add report/report.py report/template.html tests/test_report.py
git commit -m "feat: html evaluation report with confidence calibration chart"
```

---

## Task 13: Full Test Suite & Push

- [ ] **Step 1: Run the complete test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS. Fix any failures before continuing.

- [ ] **Step 2: Verify project structure**

```bash
find . -name "*.py" | grep -v __pycache__ | sort
```

Expected output includes all files from the File Structure section at the top of this plan.

- [ ] **Step 3: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 4: Verify the repo at https://github.com/JonathanReadman/agent_trade**

Confirm all files are present in the remote repo.

---

## Running the Agent

**First-time setup:**
```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and NEWS_API_KEY
pip install -r requirements.txt
```

**Run immediately (one cycle now):**
```bash
python src/scheduler.py
```

**Generate report:**
```bash
python report/report.py
open report.html
```
