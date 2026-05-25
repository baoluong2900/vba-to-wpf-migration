import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const encoder = new TextEncoder();
  
  const LAYER1_DIR = path.resolve(process.cwd(), '..', 'backend', 'workflow', 'layer1');
  const SCRIPT_PATH = path.join(LAYER1_DIR, 'run_all.py');

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(`data: {"status":"started", "message":"Initializing extraction..."}\n\n`));

      const child = spawn('python', [SCRIPT_PATH], {
        cwd: LAYER1_DIR,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });

      child.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line: string) => {
          if (line.trim()) {
            controller.enqueue(encoder.encode(`data: {"status":"running", "message":${JSON.stringify(line.trim())}}\n\n`));
          }
        });
      });

      child.stderr.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line: string) => {
          if (line.trim()) {
            controller.enqueue(encoder.encode(`data: {"status":"error", "message":${JSON.stringify(line.trim())}}\n\n`));
          }
        });
      });

      child.on('close', (code) => {
        if (code === 0) {
          controller.enqueue(encoder.encode(`data: {"status":"success", "message":"Extraction finished successfully."}\n\n`));
        } else {
          controller.enqueue(encoder.encode(`data: {"status":"failed", "message":"Process exited with code ${code}"}\n\n`));
        }
        controller.close();
      });

      child.on('error', (err) => {
        controller.enqueue(encoder.encode(`data: {"status":"failed", "message":${JSON.stringify(err.message)}}\n\n`));
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
