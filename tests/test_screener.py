"""Tier 0 screener tests: synthetic bars, no network, no LLM."""
from __future__ import annotations

import subprocess
import sys

import pandas as pd
import pytest

from agents.screener import SHORTLIST_MAX, ShortlistItem, screen


def make_bars(tickers: dict[str, tuple[list[float], list[float]]]) -> pd.DataFrame:
    """Build a (symbol, timestamp)-indexed frame from {ticker: (closes, volumes)}."""
    rows = []
    for ticker, (closes, volumes) in tickers.items():
        for i, (c, v) in enumerate(zip(closes, volumes)):
            rows.append({"symbol": ticker, "timestamp": i, "close": c, "volume": v})
    return pd.DataFrame(rows).set_index(["symbol", "timestamp"])


def flat(ticker: str = "FLAT") -> tuple[list[float], list[float]]:
    return [100.0] * 21, [1_000_000.0] * 21


def spiking() -> tuple[list[float], list[float]]:
    closes = [100.0] * 20 + [108.0]       # +8% move
    volumes = [1_000_000.0] * 20 + [4_000_000.0]  # 4x volume
    return closes, volumes


def test_spiking_ticker_ranks_above_flat() -> None:
    bars = make_bars({"SPIKE": spiking(), "FLAT": flat()})
    result = screen(bars, news_counts={"SPIKE": 12, "FLAT": 1},
                    avg_news_counts={"SPIKE": 2.0, "FLAT": 1.0}, sentiment_history={})
    assert result[0].ticker == "SPIKE"
    assert result[0].score > result[1].score


def test_shortlist_capped_at_max() -> None:
    bars = make_bars({f"T{i}": spiking() for i in range(50)})
    result = screen(bars, news_counts={}, avg_news_counts={}, sentiment_history={})
    assert len(result) == SHORTLIST_MAX


def test_prior_sentiment_carried_from_memory() -> None:
    bars = make_bars({"AAPL": spiking()})
    result = screen(bars, news_counts={}, avg_news_counts={},
                    sentiment_history={"AAPL": 0.55})
    assert result[0].prior_sentiment == 0.55


def test_single_bar_ticker_skipped() -> None:
    bars = make_bars({"NEW": ([100.0], [1_000.0]), "FLAT": flat()})
    result = screen(bars, news_counts={}, avg_news_counts={}, sentiment_history={})
    assert [i.ticker for i in result] == ["FLAT"]


def test_screener_imports_no_llm_modules() -> None:
    """Token Budget Rule 1: Tier 0 must be LLM-free. Checked in a clean interpreter
    so other test files' imports don't pollute sys.modules."""
    code = (
        "import sys; import agents.screener; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('langchain', 'langchain_core', 'langchain_anthropic', 'anthropic', 'langgraph')]; "
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
