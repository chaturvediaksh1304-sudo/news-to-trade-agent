"""Central config loaded from .env — single source for risk caps and thresholds."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class Config:
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper: bool
    anthropic_api_key: str
    max_position_pct: float
    max_daily_trades: int
    sentiment_threshold: float
    daily_token_cap: int
    db_path: Path
    dry_run: bool


def load_config() -> Config:
    return Config(
        alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
        alpaca_paper=os.getenv("ALPACA_PAPER", "true").lower() == "true",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        max_position_pct=float(os.getenv("MAX_POSITION_PCT", "5")),
        max_daily_trades=int(os.getenv("MAX_DAILY_TRADES", "10")),
        sentiment_threshold=float(os.getenv("SENTIMENT_THRESHOLD", "0.3")),
        daily_token_cap=int(os.getenv("DAILY_TOKEN_CAP", "2000000")),
        db_path=PROJECT_ROOT / os.getenv("DB_PATH", "db/trades.db"),
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
    )
