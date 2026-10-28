import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { BACKEND_LOGS_DIR } from "../../../../../lib/paths";

export async function GET() {
  try {
    // Layer 2 cost tracker writes src/backend/logs/token_log.xlsx (LOG_DIR in layer2/config.py)
    const filePath = path.join(BACKEND_LOGS_DIR, "token_log.xlsx");

    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ success: false, error: "Layer 2 token report not found. Run BD/DD agent first." }, { status: 404 });
    }

    const fileBuffer = fs.readFileSync(filePath);

    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="layer2_token_log.xlsx"',
      },
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
