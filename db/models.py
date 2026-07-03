"""Trade log + reasoning log schema. The reasoning log is the demo artifact."""
from __future__ import annotations

import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    qty: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    alpaca_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    reasoning: Mapped["ReasoningLog"] = relationship(back_populates="trade", uselist=False)


class ReasoningLog(Base):
    __tablename__ = "reasoning_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    headlines: Mapped[list] = mapped_column(JSON)  # headlines used
    sentiment_score: Mapped[float] = mapped_column(Float)
    debate_transcript: Mapped[dict] = mapped_column(JSON)  # bull/bear/risk arguments
    decision: Mapped[str] = mapped_column(String(4))  # buy | hold | sell
    confidence: Mapped[float] = mapped_column(Float)
    size_rationale: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    trade: Mapped[Trade | None] = relationship(back_populates="reasoning")


class TokenSpend(Base):
    __tablename__ = "token_spend"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)
    run_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)


class EquityPoint(Base):
    __tablename__ = "equity_curve"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), unique=True)  # YYYY-MM-DD
    equity: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)


def init_db(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Engine) -> Session:
    return Session(engine)
