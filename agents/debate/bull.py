"""Bull agent (Sonnet): argues the long case in the mesh debate."""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

PROMPT = """You are the BULL analyst in a trading debate on {ticker}.

News summary: {summary}
Sentiment score: {sentiment}
Cached fundamentals: {fundamentals}
{prior_arguments}
Make the strongest evidence-based case FOR buying {ticker} today. 3-5 sentences.
If the bull case is genuinely weak, say so honestly."""


def argue(
    ticker: str,
    summary: str,
    sentiment: float,
    fundamentals: dict | None,
    prior_arguments: str,
    llm: BaseChatModel,
) -> AIMessage:
    return llm.invoke(
        PROMPT.format(
            ticker=ticker,
            summary=summary,
            sentiment=sentiment,
            fundamentals=fundamentals or "none cached",
            prior_arguments=prior_arguments,
        )
    )
