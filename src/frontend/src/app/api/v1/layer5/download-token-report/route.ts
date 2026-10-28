import { NextResponse } from "next/server";
import fs from "fs";
import { LAYER5_TOKEN_REPORT_XLSX } from "../../../../../lib/tokenReport";

export async function GET() {
  try {
    if (!fs.existsSync(LAYER5_TOKEN_REPORT_XLSX)) {
      return NextResponse.json(
        { success: false, error: "Layer 5 token report (logs/token_report.xlsx) not found. Run an agent first." },
        { status: 404 }
      );
    }

    const fileBuffer = fs.readFileSync(LAYER5_TOKEN_REPORT_XLSX);

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
