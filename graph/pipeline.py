"""LangGraph wiring: Tier 0 screen -> Tier 1 swarm.

screen -> analyze_news -> [conditional: debate only if |delta sentiment| > threshold,
Rule 3] -> size_positions -> execute. Run with:

    python -m graph.pipeline --dry-run true    # default, no orders reach Alpaca
    python -m graph.pipeline --dry-run false   # live paper orders
"""
from __future__ import annotations

import argparse
import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents import execution, screener
from agents.debate import DebateResult, run_debate
from agents.llm import haiku, sonnet
from agents.news_analyst import NewsAnalysis, analyze
from agents.portfolio_manager import OrderPlan, plan_orders
from config import Config, load_config
from data.alpaca_client import AlpacaClient, Headline
from data.universe import get_universe
from db.models import TokenSpend, get_session, init_db
from memory.ruvector_client import MemoryClient


class PipelineState(TypedDict, total=False):
    shortlist: list[screener.ShortlistItem]
    headlines: dict[str, list[Headline]]
    last_prices: dict[str, float]
    analyses: list[NewsAnalysis]
    verdicts: list[DebateResult]
    plans: list[OrderPlan]
    executed: list[int]  # trade ids


def build_pipeline(
    alpaca: AlpacaClient,
    memory: MemoryClient,
    session: Session,
    config: Config,
):
    llm_haiku = haiku(config.anthropic_api_key)
    llm_sonnet = sonnet(config.anthropic_api_key)

    def screen_node(state: PipelineState) -> PipelineState:
        universe = get_universe()
        bars = alpaca.get_daily_bars(universe)
        news_counts = alpaca.get_news_counts(universe)
        avg_news: dict[str, float] = {}
        sentiment: dict[str, float] = {}
        for ticker in universe:
            avg_news[ticker] = memory.retrieve("sentiment-history", f"{ticker}:newscount") or 1.0
            sentiment[ticker] = memory.retrieve("sentiment-history", ticker) or 0.0
        shortlist = screener.screen(bars, news_counts, avg_news, sentiment)
        # roll the news-count average forward (80/20 blend), numeric only
        for ticker, count in news_counts.items():
            rolled = 0.8 * avg_news.get(ticker, 1.0) + 0.2 * count
            memory.store("sentiment-history", f"{ticker}:newscount", round(rolled, 3))
        last_prices = {
            item.ticker: float(bars.loc[item.ticker]["close"].iloc[-1]) for item in shortlist
        }
        return {"shortlist": shortlist, "last_prices": last_prices}

    def fetch_news_node(state: PipelineState) -> PipelineState:
        headlines = {i.ticker: alpaca.get_news(i.ticker) for i in state["shortlist"]}
        return {"headlines": headlines}

    def analyze_node(state: PipelineState) -> PipelineState:
        analyses = []
        for item in state["shortlist"]:
            ticker_headlines = state["headlines"].get(item.ticker, [])
            if not ticker_headlines:
                continue
            result = analyze(item.ticker, ticker_headlines, llm_haiku, memory, session)
            if result is not None:
                analyses.append(result)
        return {"analyses": analyses}

    def debate_gate(state: PipelineState) -> str:
        """Rule 3: no debate swarm below the sentiment-move threshold."""
        qualifying = [
            a for a in state.get("analyses", [])
            if abs(a.delta_sentiment) > config.sentiment_threshold
        ]
        return "debate" if qualifying else "skip"

    def debate_node(state: PipelineState) -> PipelineState:
        verdicts = [
            run_debate(a, llm_sonnet, memory, session)
            for a in state["analyses"]
            if abs(a.delta_sentiment) > config.sentiment_threshold
        ]
        return {"verdicts": verdicts}

    def size_node(state: PipelineState) -> PipelineState:
        plans = plan_orders(
            state.get("verdicts", []),
            equity=alpaca.get_equity(),
            positions=alpaca.get_positions(),
            last_prices=state["last_prices"],
            trades_today=execution.trades_today(session),
            config=config,
            llm=llm_sonnet,
            memory=memory,
            session=session,
        )
        return {"plans": plans}

    def execute_node(state: PipelineState) -> PipelineState:
        analyses_by_ticker = {a.ticker: a for a in state["analyses"]}
        executed = []
        for plan in state.get("plans", []):
            trade = execution.execute(
                plan,
                analyses_by_ticker[plan.ticker],
                alpaca=None if config.dry_run else alpaca,
                session=session,
                memory=memory,
                dry_run=config.dry_run,
            )
            executed.append(trade.id)
        return {"executed": executed}

    graph = StateGraph(PipelineState)
    graph.add_node("screen", screen_node)
    graph.add_node("fetch_news", fetch_news_node)
    graph.add_node("analyze_news", analyze_node)
    graph.add_node("debate", debate_node)
    graph.add_node("size_positions", size_node)
    graph.add_node("execute", execute_node)

    graph.set_entry_point("screen")
    graph.add_edge("screen", "fetch_news")
    graph.add_edge("fetch_news", "analyze_news")
    graph.add_conditional_edges("analyze_news", debate_gate, {"debate": "debate", "skip": END})
    graph.add_edge("debate", "size_positions")
    graph.add_edge("size_positions", "execute")
    graph.add_edge("execute", END)
    return graph.compile()


def check_token_cap(session: Session, config: Config) -> int:
    """Rule 6: alert if today's spend exceeds the configured cap."""
    today = datetime.date.today().isoformat()
    total = session.execute(
        select(func.sum(TokenSpend.input_tokens + TokenSpend.output_tokens)).where(
            TokenSpend.run_date == today
        )
    ).scalar_one() or 0
    if total > config.daily_token_cap:
        print(f"WARNING: daily token spend {total:,} exceeds cap {config.daily_token_cap:,}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="News-to-trade pipeline")
    parser.add_argument(
        "--dry-run", choices=["true", "false"], default="true",
        help="must be explicitly 'false' for orders to reach Alpaca (paper)",
    )
    args = parser.parse_args()

    config = load_config()
    if args.dry_run == "true":
        config = Config(**{**config.__dict__, "dry_run": True})
    else:
        config = Config(**{**config.__dict__, "dry_run": False})

    alpaca = AlpacaClient(config.alpaca_api_key, config.alpaca_secret_key, config.alpaca_paper)
    memory = MemoryClient()
    session = get_session(init_db(config.db_path))

    pipeline = build_pipeline(alpaca, memory, session, config)
    result = pipeline.invoke({})

    spend = check_token_cap(session, config)
    print(
        f"run complete — shortlist={len(result.get('shortlist', []))} "
        f"analyzed={len(result.get('analyses', []))} "
        f"debated={len(result.get('verdicts', []))} "
        f"executed={len(result.get('executed', []))} "
        f"(dry_run={config.dry_run}) tokens={spend:,}"
    )


if __name__ == "__main__":
    main()
