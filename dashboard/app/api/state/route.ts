import { NextResponse } from "next/server";
import { readState } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(readState());
  } catch {
    return NextResponse.json(
      { trades: [], days: [], reasoning: [], equity: [], lastRun: null },
      { status: 200 }
    );
  }
}
