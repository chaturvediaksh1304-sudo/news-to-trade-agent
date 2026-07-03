"""One Alpaca client: broker + market data + news, same credentials (locked decision)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass

import pandas as pd
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import (
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)


@dataclass
class Headline:
    id: str
    ticker: str
    headline: str
    summary: str
    created_at: str


@dataclass
class Position:
    ticker: str
    qty: float
    market_value: float


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True) -> None:
        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.data = StockHistoricalDataClient(api_key, secret_key)
        self.news = NewsClient(api_key, secret_key)

    # --- market data (Tier 0 inputs) ---

    def get_daily_bars(self, symbols: list[str], days: int = 25) -> pd.DataFrame:
        """Multi-symbol daily bars as a DataFrame indexed by (symbol, timestamp)."""
        start = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days * 2)
        req = StockBarsRequest(
            symbol_or_symbols=symbols, timeframe=TimeFrame.Day, start=start
        )
        return self.data.get_stock_bars(req).df

    def get_news(
        self, symbol: str, since_hours: int = 24, limit: int = 50
    ) -> list[Headline]:
        start = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=since_hours)
        req = NewsRequest(symbols=symbol, start=start, limit=limit)
        articles = self.news.get_news(req).data.get("news", [])
        return [
            Headline(
                id=str(a.id),
                ticker=symbol,
                headline=a.headline,
                summary=a.summary or "",
                created_at=a.created_at.isoformat(),
            )
            for a in articles
        ]

    def get_news_counts(self, symbols: list[str], since_hours: int = 24) -> dict[str, int]:
        """Headline count per symbol — numeric input for the Tier 0 screener."""
        return {s: len(self.get_news(s, since_hours=since_hours)) for s in symbols}

    # --- broker ---

    def get_equity(self) -> float:
        return float(self.trading.get_account().equity)

    def get_positions(self) -> list[Position]:
        return [
            Position(ticker=p.symbol, qty=float(p.qty), market_value=float(p.market_value))
            for p in self.trading.get_all_positions()
        ]

    def submit_bracket_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        limit_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> str:
        """Limit order with stop-loss/take-profit defined at execution time. Returns order id."""
        order = self.trading.submit_order(
            LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                order_class="bracket",
                stop_loss=StopLossRequest(stop_price=round(stop_loss, 2)),
                take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
            )
        )
        return str(order.id)
