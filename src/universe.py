import pandas as pd
from functools import lru_cache
import requests
from io import StringIO


@lru_cache(maxsize=1)
def get_sp500_tickers() -> list[str]:
    """Fetches current S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # Fetch with proper User-Agent header to avoid 403 Forbidden
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Parse HTML using pandas
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return tickers
