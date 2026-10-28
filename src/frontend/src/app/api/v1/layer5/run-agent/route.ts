import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs";
import { getDb, buildAccessGraph } from "../../../graph/graphBuilder";
import { buildWpfMappingFromVbaGraph, lookupFormView } from "../../../graph-wpf/wpfGraphTransform";
import { parseActualSourceGraph } from "../../../graph-wpf/source-review/sourceGraphParser";
import { LAYER5_DIR, WPF_DIR } from "../../../../../lib/paths";
import { pythonExecutable } from "../../../../../lib/python";
import { isSafeCliValue, isSafeName } from "../../../../../lib/pathSafety";
import { readLayer5TokenReport } from "../../../../../lib/tokenReport";

const execFileAsync = promisify(execFile);
const SOURCE_DIR = WPF_DIR;   // Avalonia solution root (src/wpf)
const SLN_PATH = path.join(SOURCE_DIR, "vba_brain.slnx");
const GRAPHVIEW_INPUTS_DIR = path.join(LAYER5_DIR, "agents", "graphview", "inputs");
const GRAPHVIEW_OUTPUTS_DIR = path.join(LAYER5_DIR, "agents", "graphview", "outputs");
const BUILD_FIX_MAX_ITER = 3;   // max AI fix attempts
const MAX_BUFFER = 32 * 1024 * 1024;
const VALID_AGENTS = ["ui", "logic", "service", "repo", "report", "graphview", "mapping"];
const AGENTS_WITH_FIX = new Set(["ui"]);   // only agent_ui.py implements --fix
const LOGIC_PHASES = ["all", "ui", "service"];

type ExecError = Error & { stdout?: string; stderr?: string };

// No shell anywhere: every argument goes to the child process verbatim.
function runPython(args: string[], timeout: number) {
  return execFileAsync(pythonExecutable(), args, {
    cwd: LAYER5_DIR,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    encoding: "utf8",
    timeout,
    maxBuffer: MAX_BUFFER,
    windowsHide: true,
  });
}

// ── Map generated file path → WPF source project folder ──────────────────
function resolveDestination(generatedRelPath: string): string | null {
  const p = generatedRelPath.replace(/\\/g, "/");

  if (p.startsWith("Views/"))
    return path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", p);

  if (p.startsWith("Reports/") || p.endsWith(".rdlc"))
    return path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "Views", "Reports", path.basename(p));

  if (p.startsWith("ViewModels/"))
    return path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", p);

  if (p.startsWith("Domain/Entities/"))
    return path.join(SOURCE_DIR, "vba_brain.Domain", p.replace("Domain/", ""));

  if (p.startsWith("Domain/Interfaces/"))
    return path.join(SOURCE_DIR, "vba_brain.Domain", p.replace("Domain/", ""));

  if (p.startsWith("Application/"))
    return path.join(SOURCE_DIR, "vba_brain.Application", p.replace("Application/", ""));

  if (p.startsWith("Infrastructure/"))
    return path.join(SOURCE_DIR, "vba_brain.Infrastructure", p.replace("Infrastructure/", ""));

  return null;
}

// ── List agent outputs/form_name/ and (when `copy`) copy them into the WPF source ──
function copyOutputsToSource(agent: string, formName: string, copy = true): { path: string; size: number; dest?: string; copied: boolean }[] {
  const outputDir = path.join(LAYER5_DIR, "agents", agent, "outputs", formName);
  const files: { path: string; size: number; dest?: string; copied: boolean }[] = [];

  if (!fs.existsSync(outputDir)) {
    console.warn(`[run-agent] Output dir not found: ${outputDir}`);
    return files;
  }

  // EN names for this form (fallback matching of flat output files)
  const mapped = lookupFormView(formName);
  const enViewName = mapped?.view || formName;
  const enVmName = mapped?.vm || formName;

  const walk = (dir: string, base: string): string[] => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    const result: string[] = [];
    for (const e of entries) {
      if (e.name.startsWith(".")) continue;
      const full = path.join(dir, e.name);
      const rel = path.join(base, e.name);
      if (e.isDirectory()) result.push(...walk(full, rel));
      else result.push(rel);
    }
    return result;
  };

  for (const rel of walk(outputDir, "")) {
    const srcFull = path.join(outputDir, rel);
    const fileSize = fs.statSync(srcFull).size;
    const relNorm = rel.replace(/\\/g, "/");
    const fname = path.basename(rel);

    // Skip non-code files (debug snapshots, json outputs)
    if (fname.endsWith(".json")) continue;
    let destPath: string | null = resolveDestination(relNorm);

    // Fallback: flat file in outputs root
    if (!destPath) {
      // belongsToForm: match JP name OR EN name (view or viewmodel)
      const belongsToForm =
        fname.startsWith(formName)  ||
        fname === `${formName}.cs`  ||
        fname.startsWith(enViewName) ||
        fname.startsWith(enVmName);

      if (fname.endsWith(".axaml.cs") || fname.endsWith(".xaml.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "Views", fname);
      else if (fname.endsWith(".axaml") || fname.endsWith(".xaml"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "Views", fname);
      else if (fname.endsWith(".rdlc"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "Views", "Reports", fname);
      else if (fname.endsWith("ViewModel.cs") && belongsToForm)
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "ViewModels", fname);
      else if (fname === `${formName}.cs` && agent !== "logic")
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "ViewModels", fname);
      else if (fname === `${enVmName}.cs` && agent !== "logic")
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "ViewModels", fname);
      else if (fname.endsWith("Entity.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Domain", "Entities", fname);
      else if (fname.startsWith("I") && fname.endsWith("Repository.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Domain", "Interfaces", fname);
      else if (fname.endsWith("Repository.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Infrastructure", "Persistence", "Repositories", fname);
      else if (fname.endsWith("Request.cs") || fname.endsWith("Response.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Application", "DTOs", fname);
      else if (fname.startsWith("I") && fname.endsWith("Service.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Application", "Interfaces", fname);
      else if (fname.endsWith("Service.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.Application", "Services", fname);
    }

    let copied = false;
    if (destPath && copy) {
      try {
        fs.mkdirSync(path.dirname(destPath), { recursive: true });
        fs.copyFileSync(srcFull, destPath);
        copied = true;
      } catch (copyErr: any) {
        console.error(`[run-agent] Copy failed ${rel} → ${destPath}: ${copyErr.message}`);
      }
    }

    files.push({
      path: `agents/${agent}/outputs/${formName}/${relNorm}`,
      size: fileSize,
      dest: destPath && copy ? path.relative(SOURCE_DIR, destPath).replace(/\\/g, "/") : undefined,
      copied,
    });
  }

  return files;
}

function listFlatGraphviewOutputs(formName: string): { path: string; size: number; copied: boolean }[] {
  const outputPath = path.join(GRAPHVIEW_OUTPUTS_DIR, `review_${formName}.json`);
  if (!fs.existsSync(outputPath)) return [];
  return [{
    path: `agents/graphview/outputs/review_${formName}.json`,
    size: fs.statSync(outputPath).size,
    copied: false,
  }];
}

function listMappingOutputs(formName: string = "ALL"): { path: string; size: number; dest?: string; copied: boolean }[] {
  const outputDir = path.join(LAYER5_DIR, "agents", "mapping", "outputs");
  const files: { path: string; size: number; dest?: string; copied: boolean }[] = [];

  if (!fs.existsSync(outputDir)) {
    console.warn(`[run-agent] Mapping output dir not found: ${outputDir}`);
    return files;
  }

  if (formName === "ALL") {
    const entries = fs.readdirSync(outputDir).filter(f => !f.startsWith("."));
    for (const f of entries) {
      const fullPath = path.join(outputDir, f);
      if (fs.statSync(fullPath).isDirectory()) continue;
      files.push({
        path: `agents/mapping/outputs/${f}`,
        size: fs.statSync(fullPath).size,
        dest: `docs/mappings/${f}`,
        copied: true,
      });
    }
  } else {
    // For a specific macro/module
    const targetDir = path.join(outputDir, formName);
    if (fs.existsSync(targetDir)) {
      const walk = (dir: string, base: string): string[] => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        const result: string[] = [];
        for (const e of entries) {
          if (e.name.startsWith(".")) continue;
          const full = path.join(dir, e.name);
          const rel = path.join(base, e.name);
          if (e.isDirectory()) result.push(...walk(full, rel));
          else result.push(rel);
        }
        return result;
      };

      for (const rel of walk(targetDir, "")) {
        const srcFull = path.join(targetDir, rel);
        const fileSize = fs.statSync(srcFull).size;
        const fname = path.basename(rel);
        const relNorm = rel.replace(/\\/g, "/");

        let destPath = "";
        if (fname.endsWith("Workflow.cs")) {
          // Macro Workflow
          destPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "Services", fname);
        } else if (fname.endsWith("Service.cs")) {
          // Module Service
          destPath = path.join(SOURCE_DIR, "vba_brain.Domain", "Common", fname);
        }

        let copied = false;
        if (destPath) {
          try {
            fs.mkdirSync(path.dirname(destPath), { recursive: true });
            fs.copyFileSync(srcFull, destPath);
            copied = true;
          } catch (copyErr: any) {
            console.error(`[run-agent] Copy failed ${rel} → ${destPath}: ${copyErr.message}`);
          }
        }

        files.push({
          path: `agents/mapping/outputs/${formName}/${relNorm}`,
          size: fileSize,
          dest: destPath ? path.relative(SOURCE_DIR, destPath).replace(/\\/g, "/") : undefined,
          copied,
        });
      }
    }
  }
  return files;
}

function readGraphviewReview(formName: string): any | null {
  const outputPath = path.join(GRAPHVIEW_OUTPUTS_DIR, `review_${formName}.json`);
  if (!fs.existsSync(outputPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(outputPath, "utf-8"));
  } catch {
    return null;
  }
}

async function saveGraphviewJsonToMongo(formName: string): Promise<{ file_name: string; matched: number; modified: number; upserted: boolean }[]> {
  const db = await getDb();
  const collection = db.collection("agent_graphview");
  const now = new Date();
  const files = [
    { file_name: `mapping_${formName}.json`, file_type: "mapping", file_path: path.join(GRAPHVIEW_INPUTS_DIR, `mapping_${formName}.json`) },
    { file_name: `dependency_${formName}.json`, file_type: "dependency", file_path: path.join(GRAPHVIEW_INPUTS_DIR, `dependency_${formName}.json`) },
    { file_name: `review_${formName}.json`, file_type: "review", file_path: path.join(GRAPHVIEW_OUTPUTS_DIR, `review_${formName}.json`) },
  ];

  const saved = [];
  for (const item of files) {
    if (!fs.existsSync(item.file_path)) continue;
    let content: any;
    try {
      content = JSON.parse(fs.readFileSync(item.file_path, "utf-8"));
    } catch {
      continue;
    }
    const result = await collection.updateOne(
      { file_name: item.file_name },
      {
        $setOnInsert: { created_at: now },
        $set: {
          form_name: formName,
          file_name: item.file_name,
          file_type: item.file_type,
          content,
          updated_at: now,
        },
      },
      { upsert: true }
    );
    saved.push({
      file_name: item.file_name,
      matched: result.matchedCount,
      modified: result.modifiedCount,
      upserted: Boolean(result.upsertedId),
    });
  }
  return saved;
}

async function prepareGraphviewInputs(formName: string): Promise<{ path: string; size: number; copied: boolean }[]> {
  fs.mkdirSync(GRAPHVIEW_INPUTS_DIR, { recursive: true });

  const db = await getDb();
  const graph = await buildAccessGraph(db, formName, "form");
  if (graph.success === false) {
    throw new Error(graph.error || `Cannot build VBA graph for ${formName}`);
  }

  const mapping = buildWpfMappingFromVbaGraph(
    [...graph.elements.nodes],
    [...graph.elements.edges],
    "form",
    formName
  );
  const dependency = parseActualSourceGraph(SOURCE_DIR, formName);

  const mappingPath = path.join(GRAPHVIEW_INPUTS_DIR, `mapping_${formName}.json`);
  const dependencyPath = path.join(GRAPHVIEW_INPUTS_DIR, `dependency_${formName}.json`);
  fs.writeFileSync(mappingPath, JSON.stringify(mapping, null, 2), "utf-8");
  fs.writeFileSync(dependencyPath, JSON.stringify({
    formName,
    phase: 1,
    sourceRoot: SOURCE_DIR,
    elements: { nodes: dependency.nodes, edges: dependency.edges },
    nodes: dependency.nodes,
    edges: dependency.edges,
    stats: dependency.stats,
    files: dependency.files,
  }, null, 2), "utf-8");

  return [mappingPath, dependencyPath].map((filePath) => ({
    path: `agents/graphview/inputs/${path.basename(filePath)}`,
    size: fs.statSync(filePath).size,
    copied: false,
  }));
}

// ── dotnet build → return errors if any ──────────────────────────────────
async function buildSolution(): Promise<{ success: boolean; errors: string; output: string }> {
  try {
    const { stdout, stderr } = await execFileAsync(
      "dotnet",
      ["build", SLN_PATH, "--no-restore", "-v", "minimal"],
      { encoding: "utf8", timeout: 60000, maxBuffer: MAX_BUFFER, windowsHide: true }
    );
    const combined = stdout + stderr;
    const failed = combined.includes("Build FAILED") || (combined.includes("Error(s)") && !combined.includes("0 Error(s)"));
    return { success: !failed, errors: failed ? combined : "", output: combined };
  } catch (err) {
    // dotnet build exits with non-0 on failure
    const e = err as ExecError;
    const combined = (e.stdout || "") + (e.stderr || "") || e.message;
    return { success: false, errors: combined, output: combined };
  }
}

// ── Parse dotnet error lines (trim to relevant parts) ────────────────────
function parseErrors(buildOutput: string): string {
  const lines = buildOutput.split("\n");
  const errorLines = lines.filter(l =>
    l.includes(": error ") || l.includes(": warning MC") ||
    l.includes("Build FAILED") || l.includes("Error(s)")
  );
  return errorLines.slice(0, 50).join("\n") || buildOutput.slice(-1000);
}

// ── AI fix: call agent --fix mode (build errors passed as one argv value) ─
async function aiFixErrors(agent: string, formName: string, errors: string): Promise<void> {
  const agentScriptPath = path.join(LAYER5_DIR, "agents", agent, `agent_${agent}.py`);
  try {
    await runPython([agentScriptPath, formName, `--fix=${errors}`], 120000);
  } catch (err) {
    console.error(`[run-agent] AI fix error: ${(err as Error).message}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => null);
    if (!body || typeof body !== "object") {
      return NextResponse.json({ success: false, error: "Invalid JSON body" }, { status: 400 });
    }
    const agent = body.agent;
    const form_name = agent === "mapping" ? (body.form_name || "ALL") : body.form_name;
    const model = body.model || "";
    const dryRun = Boolean(body.dry_run);

    if (!agent || !form_name) {
      return NextResponse.json({ success: false, error: "Missing agent or form_name" }, { status: 400 });
    }
    if (!VALID_AGENTS.includes(agent)) {
      return NextResponse.json({ success: false, error: `Invalid agent: ${agent}` }, { status: 400 });
    }
    if (!isSafeName(form_name)) {
      return NextResponse.json({ success: false, error: "Invalid form_name" }, { status: 400 });
    }
    if (model && !isSafeCliValue(model)) {
      return NextResponse.json({ success: false, error: "Invalid model" }, { status: 400 });
    }
    if (dryRun && agent !== "logic") {
      return NextResponse.json({ success: false, error: "dry_run is only supported by the logic agent" }, { status: 400 });
    }

    // ── Logic agent: generates the method bodies and patches them into the ViewModel ──
    if (agent === "logic") {
      const phase = body.phase ?? "all";   // default: all events (ui + service)
      if (!LOGIC_PHASES.includes(phase)) {
        return NextResponse.json({ success: false, error: `Invalid phase: ${phase}` }, { status: 400 });
      }
      const logicScript = path.join(LAYER5_DIR, "agents", "logic", "agent_logic.py");
      const logicArgs = [logicScript, form_name, "--event-class", phase];
      if (model) logicArgs.push("--model", model);
      if (dryRun) logicArgs.push("--input-only");

      const { stdout: genOut, stderr: genErr } = await runPython(logicArgs, 300_000);

      const vmFileName = `${lookupFormView(form_name)?.vm || `${form_name}ViewModel`}.cs`;
      // Copy ViewModel outputs to the WPF source to keep them in sync
      const filesCopied = copyOutputsToSource("logic", form_name);

      const vmPath = path.join(SOURCE_DIR, "vba_brain.UI.Avalonia", "ViewModels", vmFileName);
      const vmExists = fs.existsSync(vmPath);
      const files = vmExists ? [{
        path: `ViewModels/${vmFileName}`,
        size: fs.statSync(vmPath).size,
        dest: `vba_brain.UI.Avalonia/ViewModels/${vmFileName}`,
        copied: true,
      }] : filesCopied;

      return NextResponse.json({
        success: true,
        agent,
        form_name,
        phase,
        files,
        copied: files.length,
        stdout: (genOut + genErr).slice(-800),
        token_stats: readLayer5TokenReport(),
      });
    }

    // ── Step 1: Run Agent (generate files) ──────────────────────────────
    const preparedInputs = agent === "graphview" ? await prepareGraphviewInputs(form_name) : [];
    const agentScriptPath = path.join(LAYER5_DIR, "agents", agent, `agent_${agent}.py`);
    const agentArgs = [agentScriptPath, form_name];
    if (model) agentArgs.push("--model", model);
    const { stdout } = await runPython(agentArgs, 180000);

    // ── Step 2: Copy generated files → WPF source ───────────────────────
    // agent_repo.py merges and deploys repositories across forms itself, so its
    // per-form snapshots are only listed, never copied over the shared files.
    let files = agent === "graphview"
      ? listFlatGraphviewOutputs(form_name)
      : agent === "mapping"
        ? listMappingOutputs(form_name)
        : copyOutputsToSource(agent, form_name, agent !== "repo");

    // ── Step 3: Build (+ AI fix loop for agents that support --fix) ──────
    const buildLog: { iter: number; success: boolean; errors?: string }[] = [];
    const buildRan = (agent === "ui" || agent === "report") && fs.existsSync(SLN_PATH);
    let buildSuccess = true;

    if (buildRan) {
      const maxIter = AGENTS_WITH_FIX.has(agent) ? BUILD_FIX_MAX_ITER : 1;
      for (let iter = 1; iter <= maxIter; iter++) {
        console.log(`[run-agent] Build attempt ${iter}/${maxIter}...`);
        const build = await buildSolution();
        buildSuccess = build.success;
        buildLog.push({ iter, success: build.success, errors: build.success ? undefined : parseErrors(build.errors) });
        if (build.success || iter === maxIter) break;

        console.log(`[run-agent] Build FAILED — calling AI fix (attempt ${iter})...`);
        await aiFixErrors(agent, form_name, parseErrors(build.errors));
        files = copyOutputsToSource(agent, form_name);
      }
    }

    const graphviewReview = agent === "graphview" ? readGraphviewReview(form_name) : null;
    const mongoSaved = agent === "graphview" ? await saveGraphviewJsonToMongo(form_name) : [];

    return NextResponse.json({
      success: buildSuccess,
      agent,
      form_name,
      error: buildSuccess ? undefined : `dotnet build failed (${buildLog.length} attempt${buildLog.length === 1 ? "" : "s"})`,
      files,
      copied: files.filter(f => f.copied).length,
      prepared_inputs: preparedInputs,
      graphview_review: graphviewReview ? {
        status: graphviewReview.status,
        summary: graphviewReview.summary,
        issues: Array.isArray(graphviewReview.issues) ? graphviewReview.issues.slice(0, 50) : [],
        review_path: `agents/graphview/outputs/review_${form_name}.json`,
      } : null,
      mongo_saved: mongoSaved,
      build: {
        ran: buildRan,
        success: buildSuccess,
        iterations: buildLog.length,
        log: buildLog,
      },
      stdout: stdout.slice(-500),
      token_stats: readLayer5TokenReport(),
    });

  } catch (err) {
    const e = err as ExecError;
    const errorMsg = e.stderr || e.message || "Unknown error";
    return NextResponse.json({ success: false, error: String(errorMsg).slice(-800) }, { status: 500 });
  }
}
