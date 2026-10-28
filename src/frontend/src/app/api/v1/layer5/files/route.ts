import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { LAYER5_DIR } from "../../../../../lib/paths";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const agent = searchParams.get("agent");
  const type = searchParams.get("type"); // "inputs" or "outputs"
  const form = searchParams.get("form");

  if (!agent || !type) {
    return NextResponse.json({ success: false, error: "Missing agent or type param" }, { status: 400 });
  }
  if (type !== "inputs" && type !== "outputs") {
    return NextResponse.json({ success: false, error: "type must be inputs or outputs" }, { status: 400 });
  }

  const agentsRoot = path.join(LAYER5_DIR, "agents");
  const dir = path.resolve(agentsRoot, agent, type);

  // Prevent path traversal (e.g. agent="../../.." ): confine to agents root
  if (dir !== agentsRoot && !dir.startsWith(agentsRoot + path.sep)) {
    return NextResponse.json({ success: false, error: "Invalid agent or type param" }, { status: 400 });
  }

  if (!fs.existsSync(dir)) {
    return NextResponse.json({ success: false, error: `Directory not found: agents/${agent}/${type}` });
  }

  try {
    const allFiles = fs.readdirSync(dir).filter(f => !f.startsWith("."));

    // For inputs, filter by form name. For outputs, show all files.
    const filtered = (form && type === "inputs")
      ? allFiles.filter(f => f.toLowerCase().includes(form.toLowerCase()))
      : allFiles;

    const files = filtered.map(f => {
      const fullPath = path.join(dir, f);
      const stat = fs.statSync(fullPath);
      let content = "";
      // Read small files (<100KB)
      if (stat.size < 100 * 1024) {
        try { content = fs.readFileSync(fullPath, "utf-8"); } catch { content = "[binary file]"; }
      } else {
        content = `[File too large: ${(stat.size / 1024).toFixed(1)} KB]`;
      }
      return { name: f, path: `agents/${agent}/${type}/${f}`, size: stat.size, content };
    });

    return NextResponse.json({ success: true, agent, type, files });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
