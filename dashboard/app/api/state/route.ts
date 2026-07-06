import { NextResponse } from "next/server";
import demoState from "../../../lib/demo-state.json";
import { readState } from "../../../lib/db";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso.slice(0, 10) + "T00:00:00Z");
  const shifted = new Date(d.getTime() + days * DAY_MS);
  return shifted.toISOString().slice(0, 10) + iso.slice(10);
}

// The bundled snapshot has fixed dates from when it was captured. Re-anchor
// everything so the most recent trading day is always "today" — the demo
// stays current without a daily pipeline run.
function shiftDemoDates(state: typeof demoState) {
  const newest = state.days[0]?.date;
  if (!newest) return state;
  const today = new Date().toISOString().slice(0, 10);
  const delta = Math.round(
    (new Date(today + "T00:00:00Z").getTime() -
      new Date(newest + "T00:00:00Z").getTime()) /
      DAY_MS
  );
  if (delta === 0) return state;

  const shiftTrade = <T extends { created_at: string }>(t: T): T => ({
    ...t,
    created_at: shiftDate(t.created_at, delta),
  });

  return {
    ...state,
    trades: state.trades.map(shiftTrade),
    days: state.days.map((d) => ({
      ...d,
      date: shiftDate(d.date, delta),
      trades: d.trades.map(shiftTrade),
    })),
    reasoning: state.reasoning.map(shiftTrade),
    equity: state.equity.map((e) => ({ ...e, date: shiftDate(e.date, delta) })),
    lastRun: state.lastRun ? shiftDate(state.lastRun, delta) : null,
  };
}

export async function GET() {
  try {
    return NextResponse.json(readState());
  } catch {
    // no local trades.db (e.g. deployed on Vercel) — serve the bundled demo
    // snapshot, re-anchored to today
    return NextResponse.json(shiftDemoDates(demoState));
  }
}
