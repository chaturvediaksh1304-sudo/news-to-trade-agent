"""Execution agent: places Alpaca paper orders, writes the reasoning chain.

Safety: refuses to submit unless dry_run is EXPLICITLY False (bool). Dry runs
still write the full Trade + ReasoningLog rows so the demo log is complete.
"""
from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.news_analyst import NewsAnalysis
from agents.portfolio_manager import OrderPlan
from data.alpaca_client import AlpacaClient
from db.models import ReasoningLog, Trade
from memory.ruvector_client import MemoryClient


def trades_today(session: Session) -> int:
    today = datetime.date.today().isoformat()
    stmt = select(func.count(Trade.id)).where(func.date(Trade.created_at) == today)
    return session.execute(stmt).scalar_one()


def execute(
    plan: OrderPlan,
    analysis: NewsAnalysis,
    alpaca: AlpacaClient | None,
    session: Session,
    memory: MemoryClient,
    dry_run: bool,
) -> Trade:
    if dry_run is not False and alpaca is not None:
        raise ValueError("dry_run must be explicitly False for a live paper order")

    order_id: str | None = None
    if dry_run is False:
        if alpaca is None:
            raise ValueError("no Alpaca client provided for live paper order")
        order_id = alpaca.submit_bracket_order(
            ticker=plan.ticker,
            side=plan.side,
            qty=plan.qty,
            limit_price=plan.limit_price,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
        )

    trade = Trade(
        ticker=plan.ticker,
        side=plan.side,
        qty=plan.qty,
        notional=plan.notional,
        limit_price=plan.limit_price,
        stop_loss=plan.stop_loss,
        take_profit=plan.take_profit,
        dry_run=dry_run is not False,
        alpaca_order_id=order_id,
    )
    session.add(trade)
    session.flush()

    reasoning = ReasoningLog(
        trade_id=trade.id,
        ticker=plan.ticker,
        headlines=analysis.headlines_used,
        sentiment_score=analysis.sentiment,
        debate_transcript=plan.debate.transcript,
        decision=plan.debate.decision,
        confidence=plan.debate.confidence,
        size_rationale=plan.size_rationale,
    )
    session.add(reasoning)
    session.commit()

    memory.store(
        "trade-reasoning",
        f"{trade.created_at.date().isoformat()}:{plan.ticker}:{trade.id}",
        {
            "ticker": plan.ticker,
            "decision": plan.debate.decision,
            "confidence": plan.debate.confidence,
            "headlines": analysis.headlines_used,
            "sentiment": analysis.sentiment,
            "transcript": plan.debate.transcript,
            "size_rationale": plan.size_rationale,
            "dry_run": dry_run is not False,
        },
    )
    return trade
