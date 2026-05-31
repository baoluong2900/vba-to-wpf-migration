import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";

export async function GET(req: NextRequest) {
  try {
    // Layer 2 token log lives at src/backend/workflow/logs/token_log.xlsx
    const logsDir = path.resolve(process.cwd(), "..", "backend", "workflow", "logs");
    const filePath = path.join(logsDir, "token_log.xlsx");

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
