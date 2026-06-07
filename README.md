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
