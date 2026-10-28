import { NextResponse } from "next/server";
import { readLayer5TokenReport } from "../../../../../lib/tokenReport";

export const dynamic = "force-dynamic";

/** GET /api/v1/layer5/token-stats — latest Layer 5 token session (logs/token_report.json). */
export async function GET() {
  return NextResponse.json({ success: true, token_stats: readLayer5TokenReport() });
}
