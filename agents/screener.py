"""Tier 0 screener: runs on all ~500 tickers, pure numeric filters, ZERO LLM calls.

Token Budget Rule 1: never call an LLM per-ticker here. This module must not
import any LLM library.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SHORTLIST_MIN = 15
SHORTLIST_MAX = 30
TRAILING_WINDOW = 20


@dataclass
class ShortlistItem:
    ticker: str
    price_delta_pct: float   # last close vs prior close, %
    volume_ratio: float      # last volume vs trailing avg
    news_ratio: float        # today's headline count vs trailing daily avg
    prior_sentiment: float   # rolling score from sentiment-history memory
    score: float


def _signal_score(price_delta_pct: float, volume_ratio: float, news_ratio: float) -> float:
    """Composite attention score: big price move, unusual volume, unusual news flow."""
    return abs(price_delta_pct) + 2.0 * max(volume_ratio - 1.0, 0.0) + 1.5 * max(news_ratio - 1.0, 0.0)


def screen(
    bars: pd.DataFrame,
    news_counts: dict[str, int],
    avg_news_counts: dict[str, float],
    sentiment_history: dict[str, float],
) -> list[ShortlistItem]:
    """Rank all tickers by numeric signal, return the top 15-30.

    bars: DataFrame with MultiIndex (symbol, timestamp) and columns close, volume
          (the shape alpaca-py returns from get_stock_bars().df).
    """
    items: list[ShortlistItem] = []
    for ticker in bars.index.get_level_values(0).unique():
        tdf = bars.loc[ticker]
        if len(tdf) < 2:
            continue
        closes = tdf["close"]
        volumes = tdf["volume"]
        price_delta_pct = (closes.iloc[-1] / closes.iloc[-2] - 1.0) * 100.0
        trailing_vol = volumes.iloc[:-1].tail(TRAILING_WINDOW).mean()
        volume_ratio = volumes.iloc[-1] / trailing_vol if trailing_vol > 0 else 1.0
        avg_news = avg_news_counts.get(ticker, 1.0) or 1.0
        news_ratio = news_counts.get(ticker, 0) / avg_news
        items.append(
            ShortlistItem(
                ticker=str(ticker),
                price_delta_pct=round(price_delta_pct, 3),
                volume_ratio=round(volume_ratio, 3),
                news_ratio=round(news_ratio, 3),
                prior_sentiment=sentiment_history.get(ticker, 0.0),
                score=round(_signal_score(price_delta_pct, volume_ratio, news_ratio), 3),
            )
        )

    items.sort(key=lambda i: i.score, reverse=True)
    return items[:SHORTLIST_MAX] if len(items) > SHORTLIST_MAX else items
