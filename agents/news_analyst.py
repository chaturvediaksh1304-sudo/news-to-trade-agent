"""News Analyst (Haiku): batch-summarize + sentiment-score ALL headlines per ticker
in ONE call (Rule 4). Checks headline-cache before any LLM call (Rule 2).
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from agents.llm import parse_json_block, record_spend
from data.alpaca_client import Headline
from memory.ruvector_client import MemoryClient

PROMPT = """You are a financial news analyst. Below are today's headlines for {ticker}.
In ONE response, produce:
1. a 2-3 sentence summary of the aggregate news picture
2. a single sentiment score from -1.0 (very bearish) to 1.0 (very bullish)

Headlines:
{headlines}

Respond with JSON only: {{"summary": "...", "sentiment": <float>}}"""


@dataclass
class NewsAnalysis:
    ticker: str
    summary: str
    sentiment: float
    delta_sentiment: float  # vs rolling score in sentiment-history
    headlines_used: list[str]


def analyze(
    ticker: str,
    headlines: list[Headline],
    llm: BaseChatModel,
    memory: MemoryClient,
    session: Session,
) -> NewsAnalysis | None:
    """Returns None if every headline was already summarized (no LLM call made)."""
    fresh = [h for h in headlines if memory.retrieve("headline-cache", h.id) is None]
    prior = memory.retrieve("sentiment-history", ticker) or 0.0

    if not fresh:
        return None

    text = "\n".join(f"- {h.headline}: {h.summary[:200]}" for h in fresh)
    response = llm.invoke(PROMPT.format(ticker=ticker, headlines=text))
    record_spend(session, memory, "news_analyst", response)
    parsed = parse_json_block(response.content)
    sentiment = max(-1.0, min(1.0, float(parsed["sentiment"])))

    for h in fresh:
        memory.store("headline-cache", h.id, {"ticker": ticker}, ttl_days=7)
    # rolling blend: 70% new signal, 30% history
    rolled = round(0.7 * sentiment + 0.3 * float(prior), 4)
    memory.store("sentiment-history", ticker, rolled)

    return NewsAnalysis(
        ticker=ticker,
        summary=parsed["summary"],
        sentiment=sentiment,
        delta_sentiment=round(sentiment - float(prior), 4),
        headlines_used=[h.headline for h in fresh],
    )
