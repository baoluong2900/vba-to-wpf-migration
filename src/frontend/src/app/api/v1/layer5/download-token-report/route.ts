import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";

export async function GET(req: NextRequest) {
  try {
    const LAYER5_DIR = path.resolve(process.cwd(), "..", "backend", "layer5");
    const filePath = path.join(LAYER5_DIR, "logs", "token_report.xlsx");

    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ success: false, error: "Token report file not found. Run an agent first." }, { status: 404 });
    }

    const fileBuffer = fs.readFileSync(filePath);
    
    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="layer5_token_report.xlsx"',
      },
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
