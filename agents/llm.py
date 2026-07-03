"""Shared LLM helpers: model constructors + per-agent token-spend logging (Rule 6)."""
from __future__ import annotations

import datetime
import json
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from config import HAIKU_MODEL, SONNET_MODEL
from db.models import TokenSpend
from memory.ruvector_client import MemoryClient


def haiku(api_key: str) -> ChatAnthropic:
    return ChatAnthropic(model=HAIKU_MODEL, api_key=api_key, max_tokens=2000)


def sonnet(api_key: str) -> ChatAnthropic:
    return ChatAnthropic(model=SONNET_MODEL, api_key=api_key, max_tokens=3000)


def record_spend(
    session: Session, memory: MemoryClient, agent: str, response: AIMessage
) -> None:
    usage = response.usage_metadata or {}
    today = datetime.date.today().isoformat()
    session.add(
        TokenSpend(
            agent=agent,
            run_date=today,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
    )
    session.commit()
    memory.store(
        "token-spend",
        f"{today}:{agent}:{id(response)}",
        {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)},
    )


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in LLM response: {text[:200]}")
    return json.loads(match.group(0))
