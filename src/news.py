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
