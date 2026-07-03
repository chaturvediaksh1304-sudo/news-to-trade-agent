import Database from "better-sqlite3";
import path from "path";

// Shared SQLite file written by the Python pipeline (db/trades.db at repo root).
const DB_PATH =
  process.env.DB_PATH ?? path.join(process.cwd(), "..", "db", "trades.db");

export type TradeRow = {
  id: number;
  ticker: string;
  side: string;
  qty: number;
  notional: number;
  limit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  dry_run: 0 | 1;
  created_at: string;
};

export type ReasoningRow = {
  id: number;
  trade_id: number | null;
  ticker: string;
  headlines: string; // JSON
  sentiment_score: number;
  debate_transcript: string; // JSON
  decision: string;
  confidence: number;
  size_rationale: string;
  created_at: string;
};

export type EquityRow = { date: string; equity: number };

export type DaySummary = {
  date: string;
  trades: TradeRow[];
  buys: number;
  sells: number;
  notional: number;
  avgConfidence: number | null;
};

export function readState() {
  const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  try {
    const trades = db
      .prepare("SELECT * FROM trades ORDER BY created_at DESC LIMIT 50")
      .all() as TradeRow[];
    const weekTrades = db
      .prepare(
        "SELECT * FROM trades WHERE date(created_at) >= date('now', '-7 days') ORDER BY created_at DESC"
      )
      .all() as TradeRow[];
    const confidenceByDay = db
      .prepare(
        "SELECT date(created_at) AS d, AVG(confidence) AS c FROM reasoning_logs " +
          "WHERE date(created_at) >= date('now', '-7 days') GROUP BY d"
      )
      .all() as { d: string; c: number }[];
    const confMap = new Map(confidenceByDay.map((r) => [r.d, r.c]));

    const byDay = new Map<string, TradeRow[]>();
    for (const t of weekTrades) {
      const day = t.created_at.slice(0, 10);
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day)!.push(t);
    }
    const days: DaySummary[] = [...byDay.entries()]
      .sort((a, b) => (a[0] < b[0] ? 1 : -1))
      .map(([date, dayTrades]) => ({
        date,
        trades: dayTrades,
        buys: dayTrades.filter((t) => t.side === "buy").length,
        sells: dayTrades.filter((t) => t.side === "sell").length,
        notional: dayTrades.reduce((s, t) => s + t.notional, 0),
        avgConfidence: confMap.get(date) ?? null,
      }));
    const reasoning = db
      .prepare("SELECT * FROM reasoning_logs ORDER BY created_at DESC LIMIT 10")
      .all() as ReasoningRow[];
    const equity = db
      .prepare("SELECT date, equity FROM equity_curve ORDER BY date ASC")
      .all() as EquityRow[];
    const lastRun = db
      .prepare("SELECT MAX(created_at) as t FROM reasoning_logs")
      .get() as { t: string | null };
    return {
      trades,
      days,
      reasoning: reasoning.map((r) => ({
        ...r,
        headlines: JSON.parse(r.headlines),
        debate_transcript: JSON.parse(r.debate_transcript),
      })),
      equity,
      lastRun: lastRun.t,
    };
  } finally {
    db.close();
  }
}
