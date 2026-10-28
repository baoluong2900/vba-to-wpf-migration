/**
 * POST /api/v1/layer5/run-logic
 *
 * Run Agent Logic (agent_logic.py) for a form and stream its output as SSE.
 *
 * Body: { form_name, phase?, model?, dry_run? }
 * SSE:  { type:"log"|"done"|"error", ... }
 */

import { NextRequest } from "next/server";
import { spawn, type ChildProcess } from "child_process";
import path from "path";
import fs from "fs";
import { LAYER5_DIR, WPF_DIR } from "../../../../../lib/paths";
import { pythonExecutable } from "../../../../../lib/python";
import { isSafeCliValue, isSafeName } from "../../../../../lib/pathSafety";
import { logicCodeStatus, summarizeLogicMethods } from "../../../../../lib/logicSummary";
import { lookupFormView } from "../../../graph-wpf/wpfGraphTransform";

const LOGIC_PHASES = ["all", "ui", "service"];

function sseMsg(data: object): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}
function ts(): string {
  return new Date().toLocaleTimeString("vi-VN", { hour12: false });
}
function sseError(message: string, status: number): Response {
  return new Response(sseMsg({ type: "error", message }), { status, headers: { "Content-Type": "text/event-stream" } });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const {
    form_name,
    phase = "all",   // default: run all events (ui + service)
    model,
    dry_run = false,
  } = body as { form_name: string; phase?: string; model?: string; dry_run?: boolean };

  if (!form_name) return sseError("Missing form_name", 400);
  if (!isSafeName(form_name)) return sseError("Invalid form_name", 400);
  if (!LOGIC_PHASES.includes(phase)) return sseError(`Invalid phase: ${phase}`, 400);
  if (model && !isSafeCliValue(model)) return sseError("Invalid model", 400);

  const encoder = new TextEncoder();
  const env = { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" };
  let child: ChildProcess | null = null;
  let closed = false;
  // Client gone (request aborted or stream cancelled): stop the agent instead of letting it run on.
  const stop = () => {
    closed = true;
    child?.kill();
  };

  const stream = new ReadableStream({
    async start(controller) {
      const enq = (data: object) => {
        if (closed) return;
        try { controller.enqueue(encoder.encode(sseMsg(data))); } catch { closed = true; }
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

      // Spawn python (no shell) and stream its output line by line
      const runPython = (args: string[]): Promise<number> =>
        new Promise((resolve) => {
          const proc = spawn(pythonExecutable(), args, { cwd: LAYER5_DIR, env, windowsHide: true });
          child = proc;
          proc.stdout.setEncoding("utf8");
          proc.stderr.setEncoding("utf8");
          let outBuf = "", errBuf = "";
          proc.stdout.on("data", (c: string) => {
            outBuf += c;
            const parts = outBuf.split("\n"); outBuf = parts.pop() ?? "";
            parts.forEach(logLine);
          });
          proc.stderr.on("data", (c: string) => {
            errBuf += c;
            const parts = errBuf.split("\n"); errBuf = parts.pop() ?? "";
            parts.forEach(logLine);
          });
          proc.on("close", (code) => {
            if (outBuf.trim()) logLine(outBuf);
            if (errBuf.trim()) logLine(errBuf);
            child = null;
            resolve(code ?? 1);
          });
          proc.on("error", (err) => {
            logLine(`Process error: ${err.message}`);
            child = null;
            resolve(1);
          });
        });

      req.signal.addEventListener("abort", stop, { once: true });
      try {
        enq({ type: "log", level: "INFO", ts: ts(), message: `▶ Agent Logic — ${form_name} (phase=${phase})` });
        enq({ type: "log", level: "INFO", ts: ts(), message: "Running LLM generation for ViewModel methods..." });

        const logicScript = path.join(LAYER5_DIR, "agents", "logic", "agent_logic.py");
        const logicArgs = [logicScript, form_name, "--event-class", phase];
        if (dry_run) logicArgs.push("--input-only");
        if (model) logicArgs.push("--model", model);
        const exitCode = closed ? 1 : await runPython(logicArgs);
        if (closed) return;

        const vmFileName = `${lookupFormView(form_name)?.vm || `${form_name}ViewModel`}.cs`;

        // ── Read output snapshot (method_outputs.json) ────────────────────
        let methodOutputs: any[] = [];
        const outputsPath = path.join(LAYER5_DIR, "agents", "logic", "outputs", form_name, "method_outputs.json");
        try {
          if (fs.existsSync(outputsPath)) {
            const parsed = JSON.parse(fs.readFileSync(outputsPath, "utf-8"));
            if (Array.isArray(parsed)) methodOutputs = parsed;
          }
        } catch { /* ignore */ }

        // ── Read updated ViewModel from source or outputs ──────────────────
        let csContent: string | null = null;
        let csPath = path.join(WPF_DIR, "vba_brain.UI.Avalonia", "ViewModels", vmFileName);
        if (!fs.existsSync(csPath)) {
          csPath = path.join(LAYER5_DIR, "agents", "logic", "outputs", form_name, "ViewModels", vmFileName);
        }
        try { if (fs.existsSync(csPath)) csContent = fs.readFileSync(csPath, "utf-8"); } catch { /* ignore */ }

        const summary = summarizeLogicMethods(methodOutputs, exitCode);
        const patched = summary.done + summary.todo;

        enq({
          type:      "done",
          success:   exitCode === 0,
          exit_code: exitCode,
          form_name,
          phase,
          dry_run,
          summary,
          stats: {
            total:     methodOutputs.length,
            generated: patched,
            patched,
            skipped:   summary.skip,
            errors:    summary.error,
          },
          message: exitCode === 0
            ? `Patched ${patched} methods into ViewModel ${vmFileName}`
            : `agent_logic.py exited with code ${exitCode} (${summary.error} method error(s))`,
          methods: methodOutputs.map((m: any) => ({
            event_id:    m.event_id,
            notes:       m.mapped_command?.vba_event || m.notes || "",
            cs_name:     m.cs_method,
            status:      m.status,
            code_status: logicCodeStatus(m),
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
        req.signal.removeEventListener("abort", stop);
        closed = true;
        try { controller.close(); } catch { /* already cancelled */ }
      }
    },
    cancel() {
      stop();
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
