"""Tier 1 agent tests: fake LLM, in-memory DB, local memory store. No network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, select

from agents.debate import DebateResult, run_debate
from agents.execution import execute, trades_today
from agents.news_analyst import NewsAnalysis, analyze
from agents.portfolio_manager import OrderPlan, plan_orders
from config import Config
from data.alpaca_client import Headline, Position
from db.models import Base, ReasoningLog, Trade, get_session
from memory.ruvector_client import MemoryClient


class FakeLLM:
    """Returns queued responses; counts calls (for cache/batching assertions)."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def invoke(self, prompt: str) -> AIMessage:
        self.calls += 1
        return AIMessage(
            content=self.responses[min(self.calls - 1, len(self.responses) - 1)],
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return get_session(engine)


@pytest.fixture
def memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryClient:
    import memory.ruvector_client as mod
    monkeypatch.setattr(mod, "LOCAL_STORE", tmp_path / "mem")
    return MemoryClient(use_ruflo=False)


def make_config(**overrides) -> Config:
    defaults = dict(
        alpaca_api_key="k", alpaca_secret_key="s", alpaca_paper=True,
        anthropic_api_key="a", max_position_pct=5.0, max_daily_trades=10,
        sentiment_threshold=0.3, daily_token_cap=2_000_000,
        db_path=Path("/tmp/x.db"), dry_run=True,
    )
    return Config(**{**defaults, **overrides})


HEADLINES = [
    Headline(id="h1", ticker="AAPL", headline="Apple beats earnings", summary="", created_at="t"),
    Headline(id="h2", ticker="AAPL", headline="iPhone demand strong", summary="", created_at="t"),
]


def test_news_analyst_batches_all_headlines_in_one_call(session, memory) -> None:
    llm = FakeLLM([json.dumps({"summary": "good quarter", "sentiment": 0.6})])
    result = analyze("AAPL", HEADLINES, llm, memory, session)
    assert llm.calls == 1  # Rule 4: one call for N headlines
    assert result.sentiment == 0.6
    assert result.delta_sentiment == 0.6  # no prior history


def test_news_analyst_skips_llm_when_all_cached(session, memory) -> None:
    llm = FakeLLM([json.dumps({"summary": "good", "sentiment": 0.6})])
    analyze("AAPL", HEADLINES, llm, memory, session)
    result = analyze("AAPL", HEADLINES, llm, memory, session)
    assert result is None  # Rule 2: cached headlines never re-summarized
    assert llm.calls == 1


def make_analysis(delta: float = 0.6) -> NewsAnalysis:
    return NewsAnalysis(
        ticker="AAPL", summary="good quarter", sentiment=0.6,
        delta_sentiment=delta, headlines_used=["Apple beats earnings"],
    )


def test_debate_returns_verdict_and_transcript(session, memory) -> None:
    llm = FakeLLM([
        "bull case",
        "bear case",
        json.dumps({"decision": "buy", "confidence": 0.8, "reasoning": "upside outweighs"}),
    ])
    result = run_debate(make_analysis(), llm, memory, session)
    assert result.decision == "buy"
    assert result.transcript == {"bull": "bull case", "bear": "bear case", "risk": "upside outweighs"}
    assert llm.calls == 3


def make_verdict(ticker: str = "AAPL", confidence: float = 0.8) -> DebateResult:
    return DebateResult(
        ticker=ticker, decision="buy", confidence=confidence,
        transcript={"bull": "b", "bear": "r", "risk": "ok"},
    )


def pm_response(ticker: str = "AAPL", size_pct: float = 5.0) -> str:
    return json.dumps({"orders": [
        {"ticker": ticker, "approve": True, "size_pct": size_pct, "rationale": "clean book"}
    ]})


def test_position_size_clamped_to_max_pct(session, memory) -> None:
    llm = FakeLLM([pm_response(size_pct=50.0)])  # LLM tries to oversize
    plans = plan_orders(
        [make_verdict()], equity=100_000.0, positions=[], last_prices={"AAPL": 200.0},
        trades_today=0, config=make_config(), llm=llm, memory=memory, session=session,
    )
    assert plans[0].notional == 5000.0  # clamped to 5% of 100k


def test_daily_trade_cap_enforced(session, memory) -> None:
    verdicts = [make_verdict(f"T{i}") for i in range(15)]
    response = json.dumps({"orders": [
        {"ticker": f"T{i}", "approve": True, "size_pct": 5, "rationale": "ok"} for i in range(15)
    ]})
    plans = plan_orders(
        verdicts, equity=100_000.0, positions=[],
        last_prices={f"T{i}": 100.0 for i in range(15)},
        trades_today=4, config=make_config(max_daily_trades=10),
        llm=FakeLLM([response]), memory=memory, session=session,
    )
    assert len(plans) == 6  # 10 cap - 4 already traded


def test_no_llm_call_when_cap_exhausted(session, memory) -> None:
    llm = FakeLLM([pm_response()])
    plans = plan_orders(
        [make_verdict()], equity=100_000.0, positions=[], last_prices={"AAPL": 200.0},
        trades_today=10, config=make_config(), llm=llm, memory=memory, session=session,
    )
    assert plans == []
    assert llm.calls == 0


def make_plan() -> OrderPlan:
    return OrderPlan(
        ticker="AAPL", side="buy", notional=5000.0, qty=25.0, limit_price=200.0,
        stop_loss=190.0, take_profit=220.0, size_rationale="5% of book",
        debate=make_verdict(),
    )


def test_execution_refuses_without_explicit_dry_run_false(session, memory) -> None:
    with pytest.raises(ValueError, match="explicitly False"):
        execute(make_plan(), make_analysis(), alpaca=object(), session=session,
                memory=memory, dry_run=True)


def test_dry_run_writes_trade_and_reasoning_without_order(session, memory) -> None:
    trade = execute(make_plan(), make_analysis(), alpaca=None, session=session,
                    memory=memory, dry_run=True)
    assert trade.dry_run is True
    assert trade.alpaca_order_id is None
    log = session.execute(select(ReasoningLog)).scalar_one()
    assert log.trade_id == trade.id
    assert log.debate_transcript["risk"] == "ok"
    assert trades_today(session) == 1
