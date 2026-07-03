"""Risk agent (Sonnet): weighs bull vs bear and issues the debate verdict."""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

PROMPT = """You are the RISK analyst arbitrating a trading debate on {ticker}.

News summary: {summary}
Sentiment score: {sentiment}
Cached fundamentals: {fundamentals}

BULL argument:
{bull}

BEAR argument:
{bear}

Weigh both arguments. Consider downside risk first. Respond with JSON only:
{{"decision": "buy"|"hold"|"sell", "confidence": <0.0-1.0>, "reasoning": "2-3 sentences"}}"""


def arbitrate(
    ticker: str,
    summary: str,
    sentiment: float,
    fundamentals: dict | None,
    bull_argument: str,
    bear_argument: str,
    llm: BaseChatModel,
) -> AIMessage:
    return llm.invoke(
        PROMPT.format(
            ticker=ticker,
            summary=summary,
            sentiment=sentiment,
            fundamentals=fundamentals or "none cached",
            bull=bull_argument,
            bear=bear_argument,
        )
    )
