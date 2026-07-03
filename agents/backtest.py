"""Backtest / Perf agent: nightly equity snapshot + outcome patterns back to memory.

Replay mode reads only the DB and memory — zero live API calls (Testing/Safety).
"""
from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.alpaca_client import AlpacaClient
from db.models import EquityPoint, ReasoningLog, Trade
from memory.ruvector_client import MemoryClient


def snapshot_equity(session: Session, alpaca: AlpacaClient) -> EquityPoint:
    """Record today's paper-account equity as one curve point (idempotent per day)."""
    today = datetime.date.today().isoformat()
    existing = session.execute(
        select(EquityPoint).where(EquityPoint.date == today)
    ).scalar_one_or_none()
    equity = alpaca.get_equity()
    if existing:
        existing.equity = equity
        session.commit()
        return existing
    point = EquityPoint(date=today, equity=equity)
    session.add(point)
    session.commit()
    return point


def write_outcome_patterns(session: Session, memory: MemoryClient, alpaca: AlpacaClient) -> int:
    """Score each executed (non-dry-run) trade against its current mark and store a
    weighted pattern — this is how future weighting improves without manual tuning."""
    marks = {p.ticker: p.market_value / p.qty for p in alpaca.get_positions() if p.qty}
    trades = session.execute(
        select(Trade).where(Trade.dry_run.is_(False))
    ).scalars().all()
    written = 0
    for trade in trades:
        mark = marks.get(trade.ticker)
        if mark is None or not trade.limit_price:
            continue
        pnl_pct = (mark / trade.limit_price - 1.0) * (1 if trade.side == "buy" else -1)
        reasoning = session.execute(
            select(ReasoningLog).where(ReasoningLog.trade_id == trade.id)
        ).scalar_one_or_none()
        memory.store(
            "trade-reasoning",
            f"outcome:{trade.id}",
            {
                "ticker": trade.ticker,
                "side": trade.side,
                "pnl_pct": round(pnl_pct * 100, 3),
                "confidence": reasoning.confidence if reasoning else None,
                "sentiment": reasoning.sentiment_score if reasoning else None,
            },
        )
        written += 1
    return written
