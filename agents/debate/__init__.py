"""Mesh debate: bull -> bear (sees bull) -> risk (sees both). Sonnet only.

ONLY invoked when |delta sentiment| > threshold (Rule 3) — gating lives in the
pipeline's conditional edge; this module assumes the gate already passed.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from agents.debate import bear, bull, risk
from agents.llm import parse_json_block, record_spend
from agents.news_analyst import NewsAnalysis
from memory.ruvector_client import MemoryClient


@dataclass
class DebateResult:
    ticker: str
    decision: str  # buy | hold | sell
    confidence: float
    transcript: dict[str, str]  # bull / bear / risk arguments


def run_debate(
    analysis: NewsAnalysis,
    llm: BaseChatModel,
    memory: MemoryClient,
    session: Session,
) -> DebateResult:
    fundamentals = memory.retrieve("fundamentals", analysis.ticker)

    bull_msg = bull.argue(
        analysis.ticker, analysis.summary, analysis.sentiment, fundamentals, "", llm
    )
    record_spend(session, memory, "debate_bull", bull_msg)

    bear_msg = bear.argue(
        analysis.ticker, analysis.summary, analysis.sentiment, fundamentals,
        f"The BULL analyst argued:\n{bull_msg.content}\n", llm,
    )
    record_spend(session, memory, "debate_bear", bear_msg)

    risk_msg = risk.arbitrate(
        analysis.ticker, analysis.summary, analysis.sentiment, fundamentals,
        bull_msg.content, bear_msg.content, llm,
    )
    record_spend(session, memory, "debate_risk", risk_msg)
    verdict = parse_json_block(risk_msg.content)

    return DebateResult(
        ticker=analysis.ticker,
        decision=verdict["decision"],
        confidence=max(0.0, min(1.0, float(verdict["confidence"]))),
        transcript={
            "bull": bull_msg.content,
            "bear": bear_msg.content,
            "risk": verdict["reasoning"],
        },
    )
