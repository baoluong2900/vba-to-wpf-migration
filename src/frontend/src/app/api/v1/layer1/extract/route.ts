import { NextRequest, NextResponse } from 'next/server';
import { spawn, type ChildProcess } from 'child_process';
import path from 'path';
import { LAYER1_DIR } from '../../../../../lib/paths';
import { pythonExecutable } from '../../../../../lib/python';

export const dynamic = 'force-dynamic';

// run_all.py step selection. The PostgreSQL migration (DROP/CREATE of every table) is never
// part of a console run; it stays an explicit, separate action.
const SCOPES: Record<string, { args: string[]; label: string }> = {
  full: { args: ['--skip', 'layer3'], label: 'parse, seed MongoDB, Layer 2 BD/DD (PostgreSQL migration not included)' },
  ast: { args: ['--skip', 'layer2,layer3'], label: 'parse and seed MongoDB only' },
};

function stepFor(text: string): number | undefined {
  if (text.includes('Parsing Tables') || text.includes('Parsing Queries') || text.includes('Parsing Forms')) return 2;
  if (text.includes('Parsing Macros') || text.includes('Parsing Modules') || text.includes('Aggregating References')) return 3;
  if (text.includes('Seeding MongoDB')) return 4;
  if (text.includes('Generating BD & DD Specifications')) return 5;
  return undefined;
}

function levelFor(text: string): string {
  if (text.startsWith('[SUCCESS]') || text.startsWith('[DONE]')) return 'SUCCESS';
  if (text.startsWith('[WARN]')) return 'WARN';
  if (text.startsWith('[ERROR]')) return 'ERROR';
  return 'INFO';
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const scopeKey = typeof body?.scope === 'string' ? body.scope : 'full';
  const scope = SCOPES[scopeKey];
  if (!scope) {
    return NextResponse.json({ success: false, error: `Invalid scope: ${scopeKey}` }, { status: 400 });
  }

  const encoder = new TextEncoder();
  const scriptPath = path.join(LAYER1_DIR, 'run_all.py');
  let child: ChildProcess | null = null;
  let closed = false;
  const stop = () => {
    closed = true;
    child?.kill();
  };

  const stream = new ReadableStream({
    start(controller) {
      const send = (payload: object) => {
        if (closed) return;
        try { controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`)); } catch { closed = true; }
      };
      const finish = () => {
        if (closed) return;
        closed = true;
        try { controller.close(); } catch { /* already cancelled */ }
      };

      send({ type: 'log', level: 'INFO', message: `Initializing extraction: ${scope.label}...` });

      const proc = spawn(pythonExecutable(), ['-X', 'utf8', '-u', scriptPath, ...scope.args], {
        cwd: LAYER1_DIR,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        windowsHide: true,
      });
      child = proc;
      proc.stdout.setEncoding('utf8');
      proc.stderr.setEncoding('utf8');

      const onStdoutLine = (line: string) => {
        const text = line.trim();
        if (!text) return;
        const payload: { type: string; level: string; message: string; step?: number } = { type: 'log', level: levelFor(text), message: text };
        const step = stepFor(text);
        if (step !== undefined) payload.step = step;
        send(payload);
      };
      const onStderrLine = (line: string) => {
        const text = line.trim();
        if (text) send({ type: 'log', level: text.includes('Warning') ? 'WARN' : 'ERROR', message: text });
      };
      const lineReader = (onLine: (line: string) => void) => {
        let buffer = '';
        return {
          push(chunk: string) {
            buffer += chunk;
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';
            lines.forEach(onLine);
          },
          flush() {
            if (buffer) onLine(buffer);
            buffer = '';
          },
        };
      };
      const out = lineReader(onStdoutLine);
      const err = lineReader(onStderrLine);
      proc.stdout.on('data', (chunk: string) => out.push(chunk));
      proc.stderr.on('data', (chunk: string) => err.push(chunk));

      proc.on('close', (code) => {
        out.flush();
        err.flush();
        child = null;
        if (code === 0) send({ type: 'done' });
        else send({ type: 'log', level: 'ERROR', message: code === null ? 'Process was stopped' : `Process exited with code ${code}` });
        finish();
      });
      proc.on('error', (spawnErr) => {
        send({ type: 'log', level: 'ERROR', message: spawnErr.message });
        child = null;
        finish();
      });

      // Stop the process if the client aborts the connection
      req.signal.addEventListener('abort', stop, { once: true });
    },
    cancel() {
      stop();
    },
  });

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    },
  });
}
