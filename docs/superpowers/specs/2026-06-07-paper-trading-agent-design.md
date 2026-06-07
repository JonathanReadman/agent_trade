# Paper Trading Agent — Design Spec

**Date:** 2026-06-07  
**Status:** Approved  

---

## Goal

Build a paper trading agent that uses Claude as an orchestrator to reason over news sentiment and technical price signals for S&P 500 stocks. The primary research question: does an LLM agent with genuine chain-of-thought reasoning produce calibrated trading signals — i.e., do high-confidence calls actually outperform low-confidence ones?

No crypto. No penny stocks. S&P 500 only.

---

## Architecture Overview

Four layers:

1. **Scheduler** — triggers once per trading day after market close (~4:30pm ET). Checks market calendar before running; no-ops on weekends and US holidays.

2. **Tool Layer** — discrete Python functions exposed as Claude tools:
   - `get_news(ticker)` — fetches recent headlines and snippets via NewsAPI
   - `get_technicals(ticker)` — fetches price, RSI, MACD, volume via `yfinance`
   - `get_portfolio()` — returns current holdings, cash balance, open positions from SQLite
   - `execute_trade(ticker, action, confidence)` — validates and records a BUY/SELL/HOLD to the paper portfolio ledger

3. **Agent** — a Claude API call with the tool set above. Given a pre-screened watchlist of S&P 500 tickers (those with meaningful news volume in the last 24h), it works through each one, calling tools and reasoning before deciding. Chain-of-thought and final decision are logged per trade.

4. **Evaluation Layer** — a separate script that reads the trade ledger and generates a self-contained HTML report.

**Local storage:** SQLite database with two tables — `trades` and `portfolio_snapshots`.

---

## Components & Data Flow

### Daily cycle

1. Scheduler triggers with the full S&P 500 ticker list
2. News pre-screen: tickers with no news in the last 24h are skipped (conserves NewsAPI quota)
3. For each ticker that passes the screen, agent calls `get_news()` then `get_technicals()` sequentially
4. Agent reasons over both signals and outputs: action (`BUY` / `SELL` / `HOLD`) + confidence score (0.0–1.0)
5. For BUY/SELL decisions, `execute_trade()` is called:
   - Position size calculated via simplified Kelly fraction: `f = confidence - 0.5` (50% confidence = no bet, 100% = max bet)
   - Single position capped at 10% of total portfolio value
   - Trade recorded to SQLite with: ticker, action, confidence, price at signal, reasoning text, timestamp
6. End-of-day portfolio snapshot written to SQLite (total value, cash, open positions, SPY close)

### Execution price assumption

Trades are assumed to execute at the **next-day open price**. This is fetched the following morning and written back to the trade record. Slippage is not simulated in v1 but the assumption is logged explicitly.

### Data flow

```
Scheduler
  → Agent (Claude API)
      → get_news(ticker)        [NewsAPI free tier]
      → get_technicals(ticker)  [yfinance]
      → get_portfolio()         [SQLite]
      → execute_trade(...)      [SQLite]
  → Evaluation script           [SQLite → HTML report]
```

---

## Error Handling & Constraints

### API failures
- NewsAPI and yfinance calls: 3 retries with exponential backoff. Failed tickers are skipped and logged as `status=skipped` — never surfaced to the agent.
- Claude API failure mid-cycle: entire cycle is abandoned, no partial trades committed, failure logged.

### Rate limits
- NewsAPI free tier: 100 requests/day. Pre-screening by news volume keeps usage to ~40–60 requests on active days.
- yfinance: requests batched where possible; no hard rate limit.

### Input validation on `execute_trade()`
The ledger rejects any call where:
- `confidence` is outside [0.0, 1.0]
- `action` is not in `{BUY, SELL, HOLD}`
- `ticker` is not in the S&P 500 universe
- `action=SELL` and no existing long position exists for that ticker

Validation errors are logged; the agent cannot corrupt the ledger.

### Portfolio-level constraints (enforced at ledger, not agent level)
- Maximum 10% of portfolio per single position
- No shorting — SELL only exits existing long positions
- Minimum confidence of 0.6 to execute any trade; below this threshold, trade is forced to HOLD regardless of agent output

### Market calendar
- Uses `pandas_market_calendars` to skip non-trading days

---

## Evaluation & Reporting

### SQLite schema

**`trades`**
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| ticker | TEXT | |
| action | TEXT | BUY / SELL / HOLD |
| confidence | REAL | 0.0–1.0 |
| signal_price | REAL | price when agent decided |
| execution_price | REAL | next-day open (backfilled) |
| position_size_usd | REAL | |
| reasoning | TEXT | agent chain-of-thought |
| timestamp | TEXT | ISO 8601 |
| status | TEXT | executed / skipped / rejected |

**`portfolio_snapshots`**
| Column | Type | Notes |
|---|---|---|
| date | TEXT | |
| total_value_usd | REAL | |
| cash_usd | REAL | |
| open_positions | INTEGER | |
| spy_close | REAL | benchmark |

### Report metrics

| Metric | Description |
|---|---|
| Portfolio P&L % | vs. SPY benchmark over same period |
| Sharpe Ratio | annualised, using daily returns |
| Win Rate | % of closed trades that were profitable |
| Avg gain / avg loss | raw and risk-adjusted |
| Confidence calibration | scatter: confidence score vs. actual return |
| Top 10 trades | best and worst with reasoning text |

### Report format
Self-contained HTML file using `jinja2` + inline `Chart.js`. No server required — open in any browser. Generated on demand via `python report.py`.

### Primary experiment question
The confidence calibration scatter plot is the key output. If high-confidence trades cluster toward positive returns, the agent has genuine signal. A flat scatter means it doesn't — which is also a valid and useful finding.

---

## Tech Stack

| Component | Library |
|---|---|
| Agent | `anthropic` Python SDK |
| Price & technicals | `yfinance`, `pandas_ta` |
| News | NewsAPI (`newsapi-python`) |
| Market calendar | `pandas_market_calendars` |
| Storage | `sqlite3` (stdlib) |
| Reporting | `jinja2`, Chart.js (CDN inline) |
| Scheduler | `schedule` library or system cron |

---

## Out of Scope (v1)

- Intraday trading
- Slippage / transaction cost simulation
- Short selling
- Options or derivatives
- Real money execution
- Crypto or penny stocks
- Web dashboard (report is static HTML)
