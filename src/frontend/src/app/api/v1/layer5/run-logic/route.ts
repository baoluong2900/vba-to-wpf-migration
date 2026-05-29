/**
 * POST /api/layer5/run-logic
 *
 * Run Agent Logic (gen_code_behind.py) for a form — SSE streaming.
 * Two-step pipeline:
 *   1. agent_logic.py --event-class all --input-only  (build input snapshots)
 *   2. gen_code_behind.py --input-type all             (LLM gen + patch xaml.cs)
 *
 * Body: { form_name, phase?, model?, dry_run? }
 * SSE:  { type:"log"|"done"|"error", ... }
 */

import { NextRequest } from "next/server";
import { spawn, execSync } from "child_process";
import path from "path";
import fs from "fs";

const LAYER5_DIR = path.resolve(process.cwd(), "..", "backend", "layer5");
const VIEWS_DIR  = path.resolve(process.cwd(), "..", "source", "vba_brain.UI.WPF", "Views");

function sseMsg(data: object): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}
function ts(): string {
  return new Date().toLocaleTimeString("vi-VN", { hour12: false });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const {
    form_name,
    phase = "all",   // default: run all events (ui + service)
    model,
    dry_run = false,
  } = body as { form_name: string; phase?: string; model?: string; dry_run?: boolean };

  if (!form_name) {
    return new Response(sseMsg({ type: "error", message: "Missing form_name" }),
      { status: 400, headers: { "Content-Type": "text/event-stream" } });
  }

  const encoder = new TextEncoder();
  const env = { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" };

  const stream = new ReadableStream({
    async start(controller) {
      const enq = (data: object) => {
        try { controller.enqueue(encoder.encode(sseMsg(data))); } catch { /* closed */ }
      };

      const logLine = (line: string) => {
        if (!line.trim()) return;
        let level = "INFO";
        if (/error|❌|failed/i.test(line))         level = "ERROR";
        else if (/warn|⚠/i.test(line))             level = "WARN";
        else if (/✅|patched|done/i.test(line))     level = "SUCCESS";
        else if (/llm|token|http request/i.test(line)) level = "LLM";
        enq({ type: "log", level, ts: ts(), message: line.trim() });
      };

function getPythonExecutable(): string {
  const candidates = [
    '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    'python3',
    'python'
  ];
  for (const c of candidates) {
    if (c === 'python3' || c === 'python' || fs.existsSync(c)) {
      return c;
    }
  }
  return 'python3';
}

      // Helper: spawn a python process and stream its output
      const runPython = (args: string[]): Promise<number> =>
        new Promise((resolve) => {
          const pythonCmd = getPythonExecutable();
          const proc = spawn(pythonCmd, args, { cwd: LAYER5_DIR, env });
          let outBuf = "", errBuf = "";
          const flush = (buf: string) =>
            buf.split("\n").forEach(l => { if (l.trim()) logLine(l); });

          proc.stdout.on("data", (c: Buffer) => {
            outBuf += c.toString("utf-8");
            const parts = outBuf.split("\n"); outBuf = parts.pop() ?? "";
            parts.forEach(logLine);
          });
          proc.stderr.on("data", (c: Buffer) => {
            errBuf += c.toString("utf-8");
            const parts = errBuf.split("\n"); errBuf = parts.pop() ?? "";
            parts.forEach(logLine);
          });
          proc.on("close", (code) => {
            if (outBuf.trim()) logLine(outBuf);
            if (errBuf.trim()) logLine(errBuf);
            resolve(code ?? 0);
          });
          proc.on("error", (err) => {
            logLine(`Process error: ${err.message}`);
            resolve(1);
          });
        });

      try {
        enq({ type: "log", level: "INFO", ts: ts(), message: `▶ Agent Logic — ${form_name} (phase=${phase})` });

        // ── Step 1: Run ViewModel Generation Pipeline ────────────────────
        enq({ type: "log", level: "INFO", ts: ts(), message: "Running LLM generation for ViewModel methods..." });
        const logicScript = path.join(LAYER5_DIR, "agents", "logic", "agent_logic.py");
        const logicArgs = [logicScript, form_name, "--event-class", phase || "all"];
        if (dry_run) logicArgs.push("--input-only");
        if (model) logicArgs.push("--model", model);
        const exitCode = await runPython(logicArgs);

        // Try to resolve EN name from listFormJpToEn.json for ViewModel
        let vmFileName = `${form_name}ViewModel.cs`;
        const jpToEnPath = path.join(LAYER5_DIR, "agents", "graphview", "outputs", "forms", "listFormJpToEn.json");
        if (fs.existsSync(jpToEnPath)) {
          try {
            const jpToEn = JSON.parse(fs.readFileSync(jpToEnPath, "utf-8"));
            const entry = (jpToEn.items || []).find((i: any) => i.access_form_name === form_name);
            if (entry?.wpf_viewmodel_name) {
              vmFileName = `${entry.wpf_viewmodel_name}.cs`;
            }
          } catch { /* fallback */ }
        }

        // ── Read output snapshot (method_outputs.json) ────────────────────
        let methodOutputs: any[] = [];
        const outputsPath = path.join(LAYER5_DIR, "agents", "logic", "outputs", form_name, "method_outputs.json");
        try {
          if (fs.existsSync(outputsPath)) {
            methodOutputs = JSON.parse(fs.readFileSync(outputsPath, "utf-8"));
          }
        } catch { /* ignore */ }

        // ── Read updated ViewModel from source or outputs ──────────────────
        let csContent: string | null = null;
        let csPath = path.join(LAYER5_DIR, "..", "source", "vba_brain.UI.WPF", "ViewModels", vmFileName);
        if (!fs.existsSync(csPath)) {
          csPath = path.join(LAYER5_DIR, "agents", "logic", "outputs", form_name, "ViewModels", vmFileName);
        }
        try { if (fs.existsSync(csPath)) csContent = fs.readFileSync(csPath, "utf-8"); } catch { /* ignore */ }

        const success = exitCode === 0;

        enq({
          type:      "done",
          success,
          exit_code: exitCode,
          form_name,
          phase,
          dry_run,
          stats: {
            total:     methodOutputs.length,
            generated: methodOutputs.filter((m: any) => m.status === "success").length,
            patched:   methodOutputs.filter((m: any) => m.status === "success").length,
            skipped:   methodOutputs.filter((m: any) => m.status === "skipped").length,
            errors:    methodOutputs.filter((m: any) => m.status === "error").length,
          },
          summary: `Successfully patched ${methodOutputs.filter((m: any) => m.status === "success").length} methods into pure MVVM ViewModel: ${vmFileName}`,
          methods: methodOutputs.map((m: any) => ({
            event_id:    m.event_id,
            notes:       m.mapped_command?.vba_event || m.notes || "",
            cs_name:     m.cs_method,
            status:      m.status,
            code_status: m.status === "skipped" ? "SKIP" : m.status === "error" ? "ERROR" : "DONE",
            note:        m.note ?? "",
            code_preview: typeof m.code === "string" && m.code.length > 5 ? m.code.slice(0, 400) : null,
            phase_type:  m.phase_type || "all",
          })),
          cs_file:    `ViewModels/${vmFileName}`,
          cs_content: csContent,
        });

      } catch (err: any) {
        enq({ type: "error", message: err.message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type":      "text/event-stream",
      "Cache-Control":     "no-cache",
      "Connection":        "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
