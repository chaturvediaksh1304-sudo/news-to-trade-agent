"""Seed db/trades.db with sample rows so the dashboard is viewable before the
first live pipeline run. Run: python scripts/seed_demo.py"""
from __future__ import annotations

import datetime
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from db.models import EquityPoint, ReasoningLog, Trade, get_session, init_db

# (ticker, side, sentiment, confidence, headline, days_ago)
DEMO = [
    ("NVDA", "buy", 0.72, 0.85, "Nvidia beats on data-center revenue, raises guidance", 0),
    ("AAPL", "buy", 0.44, 0.70, "Apple services revenue hits record on subscription growth", 0),
    ("KO", "sell", -0.45, 0.66, "Coca-Cola flags volume weakness in North America", 1),
    ("MSFT", "buy", 0.51, 0.74, "Microsoft Azure growth re-accelerates on AI workloads", 1),
    ("META", "buy", 0.58, 0.79, "Meta ad pricing rebounds as Reels monetization improves", 1),
    ("XOM", "buy", 0.38, 0.61, "Exxon announces buyback expansion after crude rally", 2),
    ("TSLA", "sell", -0.52, 0.71, "Tesla trims delivery outlook on softer European demand", 3),
    ("JPM", "buy", 0.41, 0.68, "JPMorgan lifts net interest income guidance", 3),
    ("AMZN", "buy", 0.63, 0.81, "Amazon AWS backlog accelerates, margins expand", 4),
    ("GOOGL", "sell", -0.36, 0.62, "Alphabet faces fresh antitrust remedies over ad stack", 5),
    ("UNH", "buy", 0.35, 0.60, "UnitedHealth reaffirms outlook after medical-cost scare", 6),
    ("WMT", "buy", 0.47, 0.72, "Walmart raises forecast on grocery share gains", 6),
]


def main() -> None:
    config = load_config()
    session = get_session(init_db(config.db_path))
    if session.query(Trade).count() > 0:
        print("db already has trades — not seeding over real data")
        return

    today = datetime.date.today()
    random.seed(13)

    equity = 100_000.0
    for i in range(45, 0, -1):
        equity *= 1 + random.uniform(-0.008, 0.011)
        session.add(EquityPoint(date=(today - datetime.timedelta(days=i)).isoformat(),
                                equity=round(equity, 2)))

    for i, (ticker, side, sentiment, confidence, headline, days_ago) in enumerate(DEMO):
        created = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=days_ago, hours=2 + (i % 5)
        )
        price = round(random.uniform(60, 600), 2)
        notional = 5000.0
        trade = Trade(
            ticker=ticker, side=side, qty=round(notional / price, 4), notional=notional,
            limit_price=price,
            stop_loss=round(price * (0.95 if side == "buy" else 1.05), 2),
            take_profit=round(price * (1.10 if side == "buy" else 0.90), 2),
            dry_run=True, created_at=created,
        )
        session.add(trade)
        session.flush()
        session.add(ReasoningLog(
            trade_id=trade.id, ticker=ticker, headlines=[headline],
            sentiment_score=sentiment,
            debate_transcript={
                "bull": f"The market is underpricing the news on {ticker}: the catalyst is "
                        "durable, not a one-day pop, and positioning remains light.",
                "bear": f"Much of this move in {ticker} is already reflected in the pre-market "
                        "gap; chasing here risks buying the top of the range.",
                "risk": "Position is small relative to book, catalyst is fundamental, and the "
                        "stop is defined — favorable asymmetry at this size.",
            },
            decision=side, confidence=confidence,
            size_rationale="5.0% of book — high-confidence verdict, no sector overlap "
                           "with current holdings.",
            created_at=created,
        ))

    session.commit()
    print(f"seeded {len(DEMO)} demo trades + 45 equity points into {config.db_path}")


if __name__ == "__main__":
    main()
