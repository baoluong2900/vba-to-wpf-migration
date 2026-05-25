import { NextResponse } from 'next/server';

const BE_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * POST /api/bd-agent
 * Proxy → FastAPI POST /api/bd-agent
 * Fallback → Python run_bd_agent.py via child_process
 */
export async function POST(req: Request) {
  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON body' }, { status: 400 });
  }

  const { screenName, model, dbData } = body;

  if (!screenName) {
    return NextResponse.json({ success: false, error: 'Missing screenName' }, { status: 400 });
  }

  try {
    const res = await fetch(`${BE_URL}/api/bd-agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ screenName, model, dbData }),
      // Timeout 5 phút cho LLM xử lý file lớn
      signal: AbortSignal.timeout(300_000),
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ success: false, error: err }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);

  } catch (error: any) {
    // Fallback sang Python child_process nếu BE server chưa sẵn sàng
    return fallbackChildProcess({ screenName, model, dbData });
  }
}

// ── Fallback ──────────────────────────────────────────────────────────────
async function fallbackChildProcess(body: any) {
  const { exec } = await import('child_process');
  const { promisify } = await import('util');
  const path = await import('path');
  const execPromise = promisify(exec);

  try {
    const pyScriptDir  = path.resolve(process.cwd(), '../backend/workflow/layer2/runners');
    const pyScriptPath = path.join(pyScriptDir, 'run_bd_agent.py');
    const inputJson    = JSON.stringify(body);

    const { stdout } = await execPromise(
      `echo ${JSON.stringify(inputJson)} | python -X utf8 "${pyScriptPath}"`,
      {
        cwd: pyScriptDir,
        maxBuffer: 1024 * 1024 * 20,
        timeout: 300_000,
      }
    );

    const lines = stdout.trim().split('\n');
    let result: any = null;
    for (let i = lines.length - 1; i >= 0; i--) {
      try { result = JSON.parse(lines[i]); break; } catch { /* tiếp */ }
    }

    if (!result) throw new Error('Không parse được kết quả từ run_bd_agent.py');
    if (result.error) return NextResponse.json({ success: false, error: result.error }, { status: 500 });
    return NextResponse.json({ success: true, result: result.result, savedPath: result.savedPath });

  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 });
  }
}
