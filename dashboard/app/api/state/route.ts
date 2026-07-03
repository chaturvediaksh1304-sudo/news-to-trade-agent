import { NextResponse } from "next/server";
import demoState from "../../../lib/demo-state.json";
import { readState } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(readState());
  } catch {
    // no local trades.db (e.g. deployed on Vercel) — serve the bundled demo snapshot
    return NextResponse.json(demoState);
  }
}
