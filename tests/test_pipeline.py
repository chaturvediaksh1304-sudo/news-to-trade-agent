"""End-to-end dry-run: mocked Alpaca + fake LLMs, full graph, rows written."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, select

import graph.pipeline as pipeline_mod
from data.alpaca_client import Headline, Position
from db.models import Base, ReasoningLog, Trade, get_session
from memory.ruvector_client import MemoryClient
from tests.test_agents import FakeLLM, make_config
from tests.test_screener import flat, make_bars, spiking


class FakeAlpaca:
    def get_daily_bars(self, symbols: list[str]) -> pd.DataFrame:
        return make_bars({"NVDA": spiking(), "KO": flat()})

    def get_news_counts(self, symbols: list[str]) -> dict[str, int]:
        return {"NVDA": 10, "KO": 1}

    def get_news(self, symbol: str) -> list[Headline]:
        if symbol != "NVDA":
            return []
        return [Headline(id="n1", ticker="NVDA", headline="NVDA smashes earnings",
                         summary="records", created_at="t")]

    def get_equity(self) -> float:
        return 100_000.0

    def get_positions(self) -> list[Position]:
        return []

    def submit_bracket_order(self, **kwargs) -> str:
        raise AssertionError("dry run must never reach Alpaca")


def test_full_dry_run_writes_trade_and_reasoning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import memory.ruvector_client as mem_mod
    monkeypatch.setattr(mem_mod, "LOCAL_STORE", tmp_path / "mem")
    monkeypatch.setattr(pipeline_mod, "get_universe", lambda: ["NVDA", "KO"])

    haiku_llm = FakeLLM([json.dumps({"summary": "blowout quarter", "sentiment": 0.8})])
    sonnet_llm = FakeLLM([
        "bull case",
        "bear case",
        json.dumps({"decision": "buy", "confidence": 0.85, "reasoning": "momentum"}),
        json.dumps({"orders": [{"ticker": "NVDA", "approve": True, "size_pct": 5,
                                "rationale": "empty book"}]}),
    ])
    monkeypatch.setattr(pipeline_mod, "haiku", lambda key: haiku_llm)
    monkeypatch.setattr(pipeline_mod, "sonnet", lambda key: sonnet_llm)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = get_session(engine)
    memory = MemoryClient(use_ruflo=False)
    config = make_config(dry_run=True)

    pipeline = pipeline_mod.build_pipeline(FakeAlpaca(), memory, session, config)
    result = pipeline.invoke({})

    assert len(result["executed"]) == 1
    trade = session.execute(select(Trade)).scalar_one()
    assert trade.ticker == "NVDA" and trade.dry_run is True
    assert trade.notional == 5000.0  # 5% of 100k
    log = session.execute(select(ReasoningLog)).scalar_one()
    assert log.headlines == ["NVDA smashes earnings"]
    assert log.debate_transcript["bull"] == "bull case"
    assert pipeline_mod.check_token_cap(session, config) > 0


def test_debate_skipped_below_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import memory.ruvector_client as mem_mod
    monkeypatch.setattr(mem_mod, "LOCAL_STORE", tmp_path / "mem")
    monkeypatch.setattr(pipeline_mod, "get_universe", lambda: ["NVDA", "KO"])

    haiku_llm = FakeLLM([json.dumps({"summary": "quiet day", "sentiment": 0.1})])
    sonnet_llm = FakeLLM(["should never be called"])
    monkeypatch.setattr(pipeline_mod, "haiku", lambda key: haiku_llm)
    monkeypatch.setattr(pipeline_mod, "sonnet", lambda key: sonnet_llm)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = get_session(engine)

    pipeline = pipeline_mod.build_pipeline(
        FakeAlpaca(), MemoryClient(use_ruflo=False), session, make_config()
    )
    result = pipeline.invoke({})

    assert result.get("verdicts") is None  # graph ended at the gate
    assert sonnet_llm.calls == 0  # Rule 3: no Sonnet spend below threshold
    assert session.execute(select(Trade)).scalar_one_or_none() is None
