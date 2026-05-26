import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  return handleExtract(req);
}

export async function GET(req: NextRequest) {
  return handleExtract(req);
}

async function handleExtract(req: NextRequest) {
  const encoder = new TextEncoder();
  
  const { searchParams } = new URL(req.url);
  const sourcePath = searchParams.get('source_path') || '';
  
  const LAYER1_DIR = path.resolve(process.cwd(), '..', 'backend', 'workflow', 'layer1');
  const SCRIPT_PATH = path.join(LAYER1_DIR, 'run_all.py');

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(`data: {"type":"log", "level":"INFO", "message":"Initializing extraction for ${sourcePath}..."}\n\n`));

      const child = spawn('python3', ['-u', SCRIPT_PATH], {
        cwd: LAYER1_DIR,
        env: { ...process.env, SOURCE_PATH: sourcePath, PYTHONIOENCODING: 'utf-8' }
      });

      child.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line: string) => {
          const text = line.trim();
          if (text) {
            let step = undefined;
            if (text.includes("Parsing Tables") || text.includes("Parsing Queries") || text.includes("Parsing Forms")) {
              step = 2;
            } else if (text.includes("Parsing Macros") || text.includes("Parsing Modules") || text.includes("Aggregating References")) {
              step = 3;
            } else if (text.includes("Seeding MongoDB")) {
              step = 4;
            }
            
            const payload: any = { type: 'log', level: 'INFO', message: text };
            if (text.startsWith('[SUCCESS]') || text.startsWith('[DONE]')) {
              payload.level = 'SUCCESS';
            } else if (text.startsWith('[WARN]')) {
              payload.level = 'WARN';
            } else if (text.startsWith('[ERROR]')) {
              payload.level = 'ERROR';
            }
            if (step !== undefined) {
              payload.step = step;
            }
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
          }
        });
      });

      child.stderr.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line: string) => {
          const text = line.trim();
          if (text) {
            const level = text.includes("Warning") ? "WARN" : "ERROR";
            controller.enqueue(encoder.encode(`data: {"type":"log", "level":"${level}", "message":${JSON.stringify(text)}}\n\n`));
          }
        });
      });

      child.on('close', (code) => {
        if (code === 0) {
          controller.enqueue(encoder.encode(`data: {"type":"done"}\n\n`));
        } else {
          controller.enqueue(encoder.encode(`data: {"type":"log", "level":"ERROR", "message":"Process exited with code ${code}"}\n\n`));
        }
        controller.close();
      });

      child.on('error', (err) => {
        controller.enqueue(encoder.encode(`data: {"type":"log", "level":"ERROR", "message":${JSON.stringify(err.message)}}\n\n`));
        controller.close();
      });
      
      // Stop the process if the client aborts the connection
      req.signal.addEventListener('abort', () => {
        child.kill();
      });
    }
  });

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    },
  });
}
