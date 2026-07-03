"""S&P 500 universe: Wikipedia table scrape, cached — do not re-fetch every run."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import httpx
import pandas as pd

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
CACHE_PATH = Path(__file__).parent / "sp500_cache.json"
CACHE_MAX_AGE_DAYS = 7


def _fetch_from_wikipedia() -> list[str]:
    resp = httpx.get(WIKI_URL, headers={"User-Agent": "news-trade-agent/0.1"}, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(resp.text)
    symbols = tables[0]["Symbol"].tolist()
    # Alpaca uses dots for share classes as-is (e.g. BRK.B)
    return [str(s).strip() for s in symbols if s]


def get_universe(cache_path: Path = CACHE_PATH) -> list[str]:
    """Return S&P 500 tickers, re-fetching only if cache is older than 7 days."""
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        fetched_at = datetime.date.fromisoformat(cached["fetched_at"])
        age = (datetime.date.today() - fetched_at).days
        if age < CACHE_MAX_AGE_DAYS:
            return cached["symbols"]

    symbols = _fetch_from_wikipedia()
    cache_path.write_text(
        json.dumps({"fetched_at": datetime.date.today().isoformat(), "symbols": symbols})
    )
    return symbols
