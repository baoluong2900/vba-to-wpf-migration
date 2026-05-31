import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs";
import { getDb, buildAccessGraph } from "../../../graph/graphBuilder";
import { buildWpfMappingFromVbaGraph } from "../../../graph-wpf/wpfGraphTransform";
import { parseActualSourceGraph } from "../../../graph-wpf/source-review/sourceGraphParser";

const execAsync = promisify(exec);
const LAYER5_DIR = path.resolve(process.cwd(), "..", "backend", "workflow", "layer5");
const SOURCE_DIR = path.resolve(process.cwd(), "..", "wpf");   // Avalonia solution root (src/wpf)
const GRAPHVIEW_SOURCE_DIR = path.resolve(process.cwd(), "..", "wpf");
const SLN_PATH = path.join(SOURCE_DIR, "vba_brain.slnx");
const TEST_PROJECT_PATH = path.join(GRAPHVIEW_SOURCE_DIR, "vba_brain.Tests", "vba_brain.Tests.csproj");
const GRAPHVIEW_INPUTS_DIR = path.join(LAYER5_DIR, "agents", "graphview", "inputs");
const GRAPHVIEW_OUTPUTS_DIR = path.join(LAYER5_DIR, "agents", "graphview", "outputs");
const TEST_RESULTS_DIR = path.join(LAYER5_DIR, "agents", "test", "test-results");
const BUILD_FIX_MAX_ITER = 3;   // max AI fix attempts

type DotnetTestCase = {
  name: string;
  className: string;
  outcome: string;
  duration: string;
  output: string;
  errorMessage: string;
  stackTrace: string;
};

// ── Map generated file path → WPF source project folder ──────────────────
function resolveDestination(generatedRelPath: string): string | null {
  const p = generatedRelPath.replace(/\\/g, "/");

  if (p.startsWith("Views/"))
    return path.join(SOURCE_DIR, "vba_brain.UI.WPF", p);

  if (p.startsWith("Reports/") || p.endsWith(".rdlc"))
    return path.join(SOURCE_DIR, "vba_brain.UI.WPF", "Views", "Reports", path.basename(p));

  if (p.startsWith("ViewModels/"))
    return path.join(SOURCE_DIR, "vba_brain.UI.WPF", p);

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

// ── Copy all files from agent outputs/form_name/ → WPF source ──────────────────────
function copyOutputsToSource(agent: string, formName: string): { path: string; size: number; dest?: string; copied: boolean }[] {
  const outputDir = path.join(LAYER5_DIR, "agents", agent, "outputs", formName);
  const files: { path: string; size: number; dest?: string; copied: boolean }[] = [];

  if (!fs.existsSync(outputDir)) {
    console.warn(`[run-agent] Output dir not found: ${outputDir}`);
    return files;
  }

  // Resolve EN names for this form (for fallback matching)
  let enViewName = formName;
  let enVmName = formName;
  const jpToEnPath = path.join(LAYER5_DIR, "agents", "graphview", "outputs", "forms", "listFormJpToEn.json");
  if (fs.existsSync(jpToEnPath)) {
    try {
      const jpToEn = JSON.parse(fs.readFileSync(jpToEnPath, "utf-8"));
      const entry = (jpToEn.items || []).find((i: any) => i.access_form_name === formName);
      if (entry?.wpf_view_name)      enViewName = entry.wpf_view_name;
      if (entry?.wpf_viewmodel_name) enVmName   = entry.wpf_viewmodel_name;
    } catch { /* fallback */ }
  }

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
    if (fname.endsWith(".json")) continue;    let destPath: string | null = resolveDestination(relNorm);

    // Fallback: flat file in outputs root
    if (!destPath) {
      // belongsToForm: match JP name OR EN name (view or viewmodel)
      const belongsToForm =
        fname.startsWith(formName)  ||
        fname === `${formName}.cs`  ||
        fname.startsWith(enViewName) ||
        fname.startsWith(enVmName);

      if (fname.endsWith(".xaml.cs"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "Views", fname);
      else if (fname.endsWith(".xaml"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "Views", fname);
      else if (fname.endsWith(".rdlc"))
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "Views", "Reports", fname);
      else if (fname.endsWith("ViewModel.cs") && belongsToForm)
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "ViewModels", fname);
      else if (fname === `${formName}.cs` && agent !== "logic")
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "ViewModels", fname);
      else if (fname === `${enVmName}.cs` && agent !== "logic")
        destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "ViewModels", fname);
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
      path: `agents/${agent}/outputs/${formName}/${relNorm}`,
      size: fileSize,
      dest: destPath ? path.relative(SOURCE_DIR, destPath).replace(/\\/g, "/") : undefined,
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
          destPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "Services", fname);
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
  const dependency = parseActualSourceGraph(GRAPHVIEW_SOURCE_DIR, formName);

  const mappingPath = path.join(GRAPHVIEW_INPUTS_DIR, `mapping_${formName}.json`);
  const dependencyPath = path.join(GRAPHVIEW_INPUTS_DIR, `dependency_${formName}.json`);
  fs.writeFileSync(mappingPath, JSON.stringify(mapping, null, 2), "utf-8");
  fs.writeFileSync(dependencyPath, JSON.stringify({
    formName,
    phase: 1,
    sourceRoot: GRAPHVIEW_SOURCE_DIR,
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
    const { stdout, stderr } = await execAsync(
      `dotnet build "${SLN_PATH}" --no-restore -v minimal`,
      { timeout: 60000 }
    );
    const combined = stdout + stderr;
    const failed = combined.includes("Build FAILED") || (combined.includes("Error(s)") && !combined.includes("0 Error(s)"));
    return { success: !failed, errors: failed ? combined : "", output: combined };
  } catch (err: any) {
    // dotnet build exits with non-0 on failure
    const combined = (err.stdout || "") + (err.stderr || "");
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

function buildDotnetTestFilter(testAgents: string[] = []): string {
  const selected = testAgents.map(a => a.toLowerCase()).filter(Boolean);
  if (selected.length === 0 || selected.includes("all")) return "";

  const classNames: string[] = [];
  if (selected.includes("ui")) classNames.push("FLoginControlTests", "FLoginBindingTests");
  if (selected.includes("logic")) classNames.push("FLoginViewModelTests", "FLoginCommandTests", "FLoginFlowTests");
  if (selected.includes("service")) classNames.push("FLoginServiceTests");
  if (selected.includes("repo")) classNames.push("Integration.Repositories");
  if (selected.includes("graphview") || selected.includes("graph") || selected.includes("gv")) classNames.push("FLoginGraphViewTests");

  return classNames.map(name => `FullyQualifiedName~${name}`).join("|");
}

function xmlDecode(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function attr(block: string, name: string): string {
  const match = block.match(new RegExp(`${name}="([^"]*)"`, "i"));
  return match ? xmlDecode(match[1]) : "";
}

function tag(block: string, name: string): string {
  const match = block.match(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`, "i"));
  return match ? xmlDecode(match[1].trim()) : "";
}

function parseTrxResults(trxPath: string): DotnetTestCase[] {
  if (!fs.existsSync(trxPath)) return [];

  const trx = fs.readFileSync(trxPath, "utf-8");
  const unitTests = new Map<string, { name: string; className: string }>();
  for (const match of trx.matchAll(/<UnitTest\b[\s\S]*?<\/UnitTest>/g)) {
    const block = match[0];
    const executionMatch = block.match(/<Execution\b[^>]*id="([^"]*)"/i);
    const executionId = executionMatch ? xmlDecode(executionMatch[1]) : "";
    const name = attr(block, "name");
    const className = attr(block, "className");
    if (executionId) unitTests.set(executionId, { name, className });
  }

  const cases: DotnetTestCase[] = [];
  for (const match of trx.matchAll(/<UnitTestResult\b[\s\S]*?(?:<\/UnitTestResult>|\/>)/g)) {
    const block = match[0];
    const executionId = attr(block, "executionId");
    const meta = unitTests.get(executionId);
    cases.push({
      name: meta?.name || attr(block, "testName"),
      className: meta?.className || "",
      outcome: attr(block, "outcome") || "Unknown",
      duration: attr(block, "duration"),
      output: tag(block, "StdOut"),
      errorMessage: tag(block, "Message"),
      stackTrace: tag(block, "StackTrace"),
    });
  }

  return cases;
}

async function runDotnetTests(testAgents: string[] = []): Promise<{ ran: boolean; success: boolean; errors: string; output: string; filter: string; cases: DotnetTestCase[] }> {
  if (!fs.existsSync(TEST_PROJECT_PATH)) {
    return {
      ran: false,
      success: false,
      errors: `Test project not found: ${TEST_PROJECT_PATH}`,
      output: "",
      filter: "",
      cases: [],
    };
  }

  const filter = buildDotnetTestFilter(testAgents);
  const filterArg = filter ? ` --filter "${filter}"` : "";
  fs.mkdirSync(TEST_RESULTS_DIR, { recursive: true });
  const trxName = `agent-test-${Date.now()}.trx`;
  const trxPath = path.join(TEST_RESULTS_DIR, trxName);
  const loggerArg = ` --logger "trx;LogFileName=${trxName}" --results-directory "${TEST_RESULTS_DIR}"`;
  try {
    const { stdout, stderr } = await execAsync(
      `dotnet test "${TEST_PROJECT_PATH}" -v minimal -m:1 /nr:false${filterArg}${loggerArg}`,
      {
        cwd: GRAPHVIEW_SOURCE_DIR,
        env: { ...process.env, LAYER5_DIR },
        timeout: 120000,
      }
    );
    const combined = stdout + stderr;
    const failed = combined.includes("Failed!") || combined.includes("Test Run Failed") || combined.includes(": error ");
    return { ran: true, success: !failed, errors: failed ? parseErrors(combined) : "", output: combined, filter, cases: parseTrxResults(trxPath) };
  } catch (err: any) {
    const combined = (err.stdout || "") + (err.stderr || "");
    return { ran: true, success: false, errors: parseErrors(combined), output: combined, filter, cases: parseTrxResults(trxPath) };
  }
}

// ── AI fix: call agent --fix mode ─────────────────────────────────────────
async function aiFixErrors(agent: string, formName: string, errors: string): Promise<void> {
  const escapedErrors = errors.replace(/"/g, '\\"').replace(/\n/g, "\\n");
  const agentScriptPath = path.join(LAYER5_DIR, "agents", agent, `agent_${agent}.py`);
  const cmd = `python "${agentScriptPath}" "${formName}" --fix "${escapedErrors}"`;
  const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
  try {
    await execAsync(cmd, { cwd: LAYER5_DIR, env, timeout: 120000 });
  } catch (err: any) {
    console.error(`[run-agent] AI fix error: ${err.message}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { agent, form_name: form_name_raw, model, query_name } = body;
    const form_name = (agent === "mapping") ? (form_name_raw || "ALL") : form_name_raw;

    if (!agent || !form_name) {
      return NextResponse.json({ success: false, error: "Missing agent or form_name" }, { status: 400 });
    }

    const validAgents = ["ui", "logic", "service", "repo", "report", "graphview", "test", "mapping"];
    if (!validAgents.includes(agent)) {
      return NextResponse.json({ success: false, error: `Invalid agent: ${agent}` }, { status: 400 });
    }

    // Reject shell metacharacters — form_name/model are interpolated into shell command strings below.
    const SAFE = /^[A-Za-z0-9._\-]+$/;
    if (!SAFE.test(form_name) || (model && !SAFE.test(model))) {
      return NextResponse.json({ success: false, error: "Invalid form_name or model" }, { status: 400 });
    }

    // ── Step 1: Run Agent (generate files) ──────────────────────────────
    const preparedInputs = agent === "graphview" ? await prepareGraphviewInputs(form_name) : [];
    const modelArg = model ? ` --model "${model}"` : "";
    const dryRunArg = body.dry_run ? " --input-only" : "";

    // ── Special flow for logic agent: ViewModel patching pipeline ────────
    // We execute agent_logic.py which generates the method bodies and patches
    // them directly into the ViewModel (*ViewModel.cs) under pure MVVM guidelines.
    if (agent === "logic") {
      const phase = (body.phase as string) || "all";   // default: all events (ui + service)
      const logicEnv = { ...process.env, PYTHONIOENCODING: "utf-8" };

      const logicScript = path.join(LAYER5_DIR, "agents", "logic", "agent_logic.py");
      const logicArgs: string[] = [`"${form_name}"`, "--event-class", `"${phase}"` || "all"];
      if (model) logicArgs.push("--model", `"${model}"`);
      if (body.dry_run) logicArgs.push("--input-only");
      
      const logicCmd = `python "${logicScript}" ${logicArgs.join(" ")}`;
      console.log(`[run-agent] Logic execution: ${logicCmd}`);

      const { stdout: genOut, stderr: genErr } = await execAsync(logicCmd, {
        cwd: LAYER5_DIR, env: logicEnv, timeout: 300_000,
      });

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
        } catch { /* fallback to JP name */ }
      }

      // Automatically copy ViewModel outputs to WPF source just to make sure they are synced
      const filesCopied = copyOutputsToSource("logic", form_name);

      const vmPath = path.join(SOURCE_DIR, "vba_brain.UI.WPF", "ViewModels", vmFileName);
      const vmExists = fs.existsSync(vmPath);
      const files = vmExists ? [{
        path: `ViewModels/${vmFileName}`,
        size: fs.statSync(vmPath).size,
        dest: `vba_brain.UI.WPF/ViewModels/${vmFileName}`,
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
        token_stats: (() => {
          try {
            const p = path.join(LAYER5_DIR, "logs", "token_report.json");
            return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : null;
          } catch { return null; }
        })(),
      });
    }
    const testAgents = Array.isArray(body.test_agents)
      ? body.test_agents.map((a: any) => String(a))
      : (typeof body.test_agents === "string" ? body.test_agents.split(",").map((a: string) => a.trim()) : []);
    const testAgentsArg = agent === "test" && testAgents.length > 0 ? ` --agents "${testAgents.join(",")}"` : "";

    const agentScriptPath = path.join(LAYER5_DIR, "agents", agent, `agent_${agent}.py`);
    const cmd = `python "${agentScriptPath}" "${form_name}"${modelArg}${dryRunArg}${testAgentsArg}`;
    const env = { ...process.env, PYTHONIOENCODING: "utf-8" };

    const { stdout, stderr } = await execAsync(cmd, {
      cwd: LAYER5_DIR,
      env,
      timeout: 180000,
    });

    // ── Step 2: Copy generated files → WPF source ───────────────────────
    let files = agent === "graphview"
      ? listFlatGraphviewOutputs(form_name)
      : agent === "mapping"
        ? listMappingOutputs(form_name)
        : copyOutputsToSource(agent, form_name);

    // ── Step 3: Build + AI Fix Loop (UI agent only, when solution exists) ──
    const buildLog: { iter: number; success: boolean; errors?: string }[] = [];
    let buildSuccess = true;

    if ((agent === "ui" || agent === "report") && fs.existsSync(SLN_PATH)) {
      for (let iter = 1; iter <= BUILD_FIX_MAX_ITER; iter++) {
        console.log(`[run-agent] Build attempt ${iter}/${BUILD_FIX_MAX_ITER}...`);
        const build = await buildSolution();
        buildSuccess = build.success;

        buildLog.push({ iter, success: build.success, errors: build.success ? undefined : parseErrors(build.errors) });

        if (build.success) {
          console.log(`[run-agent] Build SUCCESS on attempt ${iter}`);
          break;
        }

        if (iter < BUILD_FIX_MAX_ITER) {
          console.log(`[run-agent] Build FAILED — calling AI fix (attempt ${iter})...`);
          const errors = parseErrors(build.errors);
          await aiFixErrors(agent, form_name, errors);

          // Re-copy fixed files
          files = copyOutputsToSource(agent, form_name);
        }
      }
    }

    const graphviewReview = agent === "graphview" ? readGraphviewReview(form_name) : null;
    const mongoSaved = agent === "graphview" ? await saveGraphviewJsonToMongo(form_name) : [];
    const testRun = agent === "test" && !body.dry_run
      ? await runDotnetTests(testAgents)
      : { ran: false, success: true, errors: "", output: "", filter: "", cases: [] };
    const agentSuccess = !(agent === "test" && testRun.ran && !testRun.success);
    const agentError = agent === "test" && testRun.ran && !testRun.success
      ? `dotnet test FAILED. ${testRun.errors || "See test output for details."}`
      : undefined;

    return NextResponse.json({
      success: agentSuccess,
      agent,
      form_name,
      error: agentError,
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
        ran: agent === "ui" && fs.existsSync(SLN_PATH),
        success: buildSuccess,
        iterations: buildLog.length,
        log: buildLog,
      },
      tests: {
        ran: testRun.ran,
        success: testRun.success,
        errors: testRun.errors ? testRun.errors.slice(0, 2000) : "",
        output: testRun.output ? testRun.output.slice(-2000) : "",
        filter: testRun.filter,
        project: path.relative(GRAPHVIEW_SOURCE_DIR, TEST_PROJECT_PATH).replace(/\\/g, "/"),
        cases: testRun.cases,
      },
      stdout: stdout.slice(-500),
      token_stats: (() => {
        try {
          const reportPath = path.join(LAYER5_DIR, "logs", "token_report.json");
          if (fs.existsSync(reportPath)) {
            return JSON.parse(fs.readFileSync(reportPath, "utf-8"));
          }
        } catch (e) {
          console.error("[run-agent] Failed to read token stats:", e);
        }
        return null;
      })(),
    });

  } catch (err: any) {
    const errorMsg = err.stderr || err.message || "Unknown error";
    return NextResponse.json({ success: false, error: errorMsg.slice(0, 500) }, { status: 500 });
  }
}
