"""Portfolio / Risk Manager (Sonnet): position sizing, exposure caps, book check.

Hard caps (5% per name, max daily trades) are enforced IN CODE — the LLM reviews
and can only shrink or reject, never exceed. One batched call for all candidates.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from agents.debate import DebateResult
from agents.llm import parse_json_block, record_spend
from config import Config
from data.alpaca_client import Position
from memory.ruvector_client import MemoryClient

STOP_LOSS_PCT = 0.05    # 5% below entry
TAKE_PROFIT_PCT = 0.10  # 10% above entry

PROMPT = """You are the portfolio risk manager for a paper-trading book.

Account equity: ${equity:,.0f}
Current positions: {positions}
Max position size: {max_pct}% per name. Trades remaining today: {remaining}.

Candidate orders from the analyst debate (already capped in size):
{candidates}

For each candidate, decide approve or reject, considering concentration vs. the
current book (avoid doubling up on names/sectors already held) and confidence.
Respond with JSON only:
{{"orders": [{{"ticker": "...", "approve": true|false, "size_pct": <0-{max_pct}>, "rationale": "1-2 sentences"}}]}}"""


@dataclass
class OrderPlan:
    ticker: str
    side: str
    notional: float
    qty: float
    limit_price: float
    stop_loss: float
    take_profit: float
    size_rationale: str
    debate: DebateResult


def plan_orders(
    verdicts: list[DebateResult],
    equity: float,
    positions: list[Position],
    last_prices: dict[str, float],
    trades_today: int,
    config: Config,
    llm: BaseChatModel,
    memory: MemoryClient,
    session: Session,
) -> list[OrderPlan]:
    held = {p.ticker for p in positions}
    actionable = [
        v for v in verdicts
        if v.decision == "buy" and v.ticker not in held
        or v.decision == "sell" and v.ticker in held
    ]
    remaining = max(0, config.max_daily_trades - trades_today)
    if not actionable or remaining == 0:
        return []

    candidates_text = "\n".join(
        f"- {v.ticker}: {v.decision} (confidence {v.confidence:.2f}) — {v.transcript['risk']}"
        for v in actionable
    )
    positions_text = (
        ", ".join(f"{p.ticker} (${p.market_value:,.0f})" for p in positions) or "none"
    )
    response = llm.invoke(
        PROMPT.format(
            equity=equity,
            positions=positions_text,
            max_pct=config.max_position_pct,
            remaining=remaining,
            candidates=candidates_text,
        )
    )
    record_spend(session, memory, "portfolio_manager", response)
    reviews = {o["ticker"]: o for o in parse_json_block(response.content)["orders"]}

    plans: list[OrderPlan] = []
    for v in sorted(actionable, key=lambda v: v.confidence, reverse=True):
        if len(plans) >= remaining:
            break
        review = reviews.get(v.ticker)
        if not review or not review["approve"]:
            continue
        price = last_prices.get(v.ticker)
        if not price or price <= 0:
            continue
        # hard clamp: LLM can only shrink, never exceed the cap
        size_pct = min(float(review["size_pct"]), config.max_position_pct)
        notional = equity * size_pct / 100.0
        qty = round(notional / price, 4)
        if qty <= 0:
            continue
        sl = price * (1 - STOP_LOSS_PCT) if v.decision == "buy" else price * (1 + STOP_LOSS_PCT)
        tp = price * (1 + TAKE_PROFIT_PCT) if v.decision == "buy" else price * (1 - TAKE_PROFIT_PCT)
        plans.append(
            OrderPlan(
                ticker=v.ticker,
                side=v.decision,
                notional=round(notional, 2),
                qty=qty,
                limit_price=price,
                stop_loss=round(sl, 2),
                take_profit=round(tp, 2),
                size_rationale=f"{size_pct:.1f}% of book — {review['rationale']}",
                debate=v,
            )
        )
    return plans
