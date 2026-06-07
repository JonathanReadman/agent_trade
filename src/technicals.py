import time
from dataclasses import dataclass
from typing import Optional
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD


@dataclass
class TechnicalsResult:
    ticker: str
    close_price: float
    volume: int
    rsi: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    price_change_pct: Optional[float]


def get_technicals(ticker: str, max_retries: int = 3) -> Optional[TechnicalsResult]:
    last_error = None
    for attempt in range(max_retries):
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return None

            close = df["Close"].squeeze()  # ensure Series not DataFrame

            latest_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2]) if len(close) > 1 else latest_close
            price_change_pct = (latest_close - prev_close) / prev_close * 100

            rsi_val = None
            try:
                rsi_indicator = RSIIndicator(close=close, window=14)
                rsi_val = float(rsi_indicator.rsi().iloc[-1])
            except Exception:
                pass

            macd_val = None
            macd_signal_val = None
            try:
                macd_indicator = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
                macd_val = float(macd_indicator.macd().iloc[-1])
                macd_signal_val = float(macd_indicator.macd_signal().iloc[-1])
            except Exception:
                pass

            return TechnicalsResult(
                ticker=ticker,
                close_price=latest_close,
                volume=int(df["Volume"].squeeze().iloc[-1]),
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
