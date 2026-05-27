"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import Link from "next/link";
import { Play, Eye, Cpu, Settings2, DatabaseZap, BarChart3, Download, Brain, Loader2, CheckCircle, AlertCircle, Search, ChevronDown, ChevronRight, Terminal, Bot, FileSpreadsheet, Database, Sparkles } from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
// @ts-ignore
import { ReactFlow, Controls, Background, Node, Edge, useNodesState, useEdgesState, BackgroundVariant } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { L5AgentNode } from "../../components/nodes/L5AgentNode";

// ── Types ─────────────────────────────────────
interface AgentDef { key: string; label: string; icon: string; color: string; description: string; inputs: string[]; outputs: string[]; defaultModel: string; }
interface AgentRunStatus { status: "idle" | "running" | "success" | "error"; message?: string; files?: { path: string; size?: number }[]; duration?: number; }
interface LogEntry { time: string; level: string; message: string; agent?: string; }
interface ModelOption { id: string; label: string; provider: string; }

// Logic Console types
type LogicPhase = "all" | "ui" | "service";
type LogicCodeStatus = "DONE" | "TODO" | "EMPTY" | "SKIP" | "ERROR";
interface LogicLogEntry { ts: string; level: string; message: string; }
interface LogicMethod {
  event_id: string; notes: string; cs_name: string | null;
  status: string; code_status: LogicCodeStatus; note: string;
  code_preview: string | null; phase_type?: string;
}
interface LogicSummary { done: number; todo: number; skip: number; error: number; compile_ok: boolean; }
const LOGIC_CODE_CFG: Record<LogicCodeStatus, { icon: string; color: string; bg: string }> = {
  DONE: { icon: "✅", color: "#10b981", bg: "#10b98118" },
  TODO: { icon: "⚠️", color: "#f59e0b", bg: "#f59e0b18" },
  EMPTY: { icon: "⚠️", color: "#f59e0b", bg: "#f59e0b18" },
  SKIP: { icon: "⏭", color: "var(--text-muted)", bg: "#6b728018" },
  ERROR: { icon: "❌", color: "#ef4444", bg: "#ef444418" },
};
interface TokenStats {
  timestamp: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  records: {
    form_name: string;
    agent: string;
    task_type: string;
    model_id: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost_usd: number;
    timestamp: string;
  }[];
}
interface TestRunResult {
  agent: string;
  formName: string;
  timestamp: string;
  duration: number;
  ran: boolean;
  success: boolean;
  errors: string;
  output: string;
  filter: string;
  project: string;
  cases: {
    name: string;
    className: string;
    outcome: string;
    duration: string;
    output: string;
    errorMessage: string;
    stackTrace: string;
  }[];
}

// ── Agent Definitions ─────────────────────────
const AGENTS: AgentDef[] = [
  { key: "mapping",  label: "Agent Mapping",   icon: "🗺️", color: "#a855f7", description: "Common Macro/Module Mapping",      inputs: ["Layer 1 DB"],                    outputs: ["docs/mappings/*.json"],                  defaultModel: "deepseek-v4-flash" },
  { key: "repo",     label: "Agent Repo",      icon: "🗃️", color: "#f59e0b", description: "Entity, DTO, Repository",          inputs: ["DD queries", "Table schemas"],    outputs: ["Entity.cs", "DTO.cs", "Repository.cs"],  defaultModel: "qwen3-coder-480b-a35b-instruct" },
  { key: "service",  label: "Agent Service",   icon: "⚙️", color: "#3b82f6", description: "IService, Service.cs",             inputs: ["DD detail_specs", "Repo outputs"], outputs: ["IService.cs", "Service.cs"],             defaultModel: "qwen3-235b-a22b-instruct-2507" },
  { key: "logic",    label: "Agent Logic",     icon: "🧠", color: "#8b5cf6", description: "Code-behind UI events → xaml.cs",  inputs: ["F_Login_ui.json", "xaml.cs stubs"], outputs: ["xaml.cs (patched)"],                  defaultModel: "qwen3-235b-a22b-instruct-2507" },
  { key: "ui",       label: "Agent UI",        icon: "🎨", color: "#ec4899", description: "WPF XAML View",                   inputs: ["BD layout", "MongoDB controls"],  outputs: ["Window.xaml"],                           defaultModel: "deepseek-v4-pro" },
  { key: "report",   label: "Agent Report",    icon: "📊", color: "#f97316", description: "WPF Report RDLC/XAML",            inputs: ["BD layout", "DD report specs"],   outputs: ["Report.xaml", "Report.rdlc"],            defaultModel: "deepseek-v4-pro" },
  { key: "graphview",label: "Agent GraphView", icon: "🔍", color: "#6366f1", description: "Mapping + Dependency",             inputs: ["FE graph", "All outputs"],        outputs: ["mapping.json", "dependency.json"],       defaultModel: "deepseek-v4-flash" },
  { key: "test",     label: "Agent Test",      icon: "🧪", color: "#10b981", description: "Test + Golden Master",            inputs: ["BD/DD JSON", "All C#/XAML"],      outputs: ["Tests/*.cs", "certificate.json"],        defaultModel: "deepseek-v4-flash" },
];

const PIPELINE_ORDER = ["repo", "service", "logic", "ui", "graphview", "test"];

// ── Node Positions ────────────────────────────
// Form mode: full pipeline (Repo → Service → Logic → UI → GraphView → Test)
const NODE_POSITIONS_FORM: Record<string, { x: number; y: number }> = {
  repo:      { x: 50,   y: 20  },
  service:   { x: 370,  y: 20  },
  logic:     { x: 690,  y: 20  },
  ui:        { x: 1010, y: 20  },
  graphview: { x: 430,  y: 310 },
  test:      { x: 430,  y: 590 },
};

// Report mode: same layout but Agent Report replaces Agent UI
const NODE_POSITIONS_REPORT: Record<string, { x: number; y: number }> = {
  repo:      { x: 50,   y: 20  },
  service:   { x: 370,  y: 20  },
  logic:     { x: 690,  y: 20  },
  report:    { x: 1010, y: 20  },
  graphview: { x: 430,  y: 310 },
  test:      { x: 430,  y: 590 },
};

// Macro/Module mode: Mapping → Repo (side by side)
const NODE_POSITIONS_MACRO: Record<string, { x: number; y: number }> = {
  mapping: { x: 50,  y: 20 },
  repo:    { x: 370, y: 20 },
};

// ── Main ──────────────────────────────────────
export default function Layer5Page() {
  const [screenName, setScreenName] = useState("");
  const [macroModuleName, setMacroModuleName] = useState("");
  const [mappingType, setMappingType] = useState<"all" | "macro" | "module">("all");
  const [dbScreens, setDbScreens] = useState<{ key: string; name: string; type?: string }[]>([]);
  const [queryName, setQueryName] = useState("");
  const [dbQueries, setDbQueries] = useState<{ name: string }[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentRunStatus>>({});
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});
  const [testAgentFilter, setTestAgentFilter] = useState("all");
  const [modelList, setModelList] = useState<ModelOption[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [previewContent, setPreviewContent] = useState<{ title: string; content: string } | null>(null);
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);
  const [testResult, setTestResult] = useState<TestRunResult | null>(null);
  const [rightTab, setRightTab] = useState<"logs" | "preview" | "tests" | "tokens" | "logic">("logs");
  const [sidebarWidth, setSidebarWidth] = useState(420);
  const [terminalCollapsed, setTerminalCollapsed] = useState(false);

  // Logic Console state
  const [logicPhase, setLogicPhase] = useState<LogicPhase>("all");
  const [logicRunning, setLogicRunning] = useState(false);
  const [logicLogs, setLogicLogs] = useState<LogicLogEntry[]>([]);
  const [logicMethods, setLogicMethods] = useState<LogicMethod[]>([]);
  const [logicSummary, setLogicSummary] = useState<LogicSummary | null>(null);
  const [logicPreview, setLogicPreview] = useState<{ title: string; content: string } | null>(null);
  const [logicDryRun, setLogicDryRun] = useState(false);
  const logicAbortRef = useRef<AbortController | null>(null);
  const logicLogsEndRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const nodeTypes = useMemo(() => ({ l5AgentNode: L5AgentNode }), []);

  // Init agent statuses + default models
  useEffect(() => {
    const init: Record<string, AgentRunStatus> = {};
    const initModels: Record<string, string> = {};
    AGENTS.forEach(a => {
      init[a.key] = { status: "idle" };
      initModels[a.key] = a.defaultModel;
    });
    setAgentStatuses(init);
    setAgentModels(initModels);
  }, []);

  // Fetch model list from config API
  useEffect(() => {
    fetch("/api/v1/layer2/config").then(r => r.json()).then(d => {
      if (d.models && Array.isArray(d.models)) {
        setModelList(d.models);
        addLog("INFO", `Loaded ${d.models.length} models from config`);
      }
    }).catch(() => { });
  }, []);

  const addLog = useCallback((level: string, message: string, agent?: string) => {
    const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });
    setLogs(prev => [...prev, { time, level, message, agent }]);
  }, []);

  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);
  useEffect(() => { logicLogsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logicLogs]);

  const runLogicAgent = useCallback(async () => {
    if (logicRunning) { logicAbortRef.current?.abort(); setLogicRunning(false); return; }
    if (!screenName) { addLog("WARN", "Select a form first"); return; }
    const logicModel = agentModels["logic"] || AGENTS.find(a => a.key === "logic")?.defaultModel || "";
    setLogicRunning(true);
    setLogicLogs([]);
    setLogicMethods([]);
    setLogicSummary(null);
    setRightTab("logic");
    const ctrl = new AbortController();
    logicAbortRef.current = ctrl;
    try {
      const resp = await fetch("/api/v1/layer5/run-logic", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ form_name: screenName, phase: logicPhase, model: logicModel, dry_run: logicDryRun }),
        signal: ctrl.signal,
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split("\n\n"); buf = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const ev = JSON.parse(line);
            const t = new Date().toLocaleTimeString("vi-VN", { hour12: false });
            if (ev.type === "log") {
              setLogicLogs(prev => [...prev, { ts: ev.ts ?? t, level: ev.level ?? "INFO", message: ev.message }]);
            } else if (ev.type === "done") {
              setLogicMethods(ev.methods ?? []);
              setLogicSummary(ev.summary ?? null);
              if (ev.cs_content) setLogicPreview({ title: ev.cs_file, content: ev.cs_content });
              const ok = ev.success;
              addLog(ok ? "SUCCESS" : "ERROR", `[logic] ${ok ? "✅" : "❌"} ${screenName} — ${ev.stats?.patched ?? 0} patched, ${ev.stats?.skipped ?? 0} skipped`, "logic");
              setAgentStatuses(prev => ({ ...prev, logic: { status: ok ? "success" : "error" } }));
            } else if (ev.type === "error") {
              setLogicLogs(prev => [...prev, { ts: t, level: "ERROR", message: ev.message }]);
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        const t = new Date().toLocaleTimeString("vi-VN", { hour12: false });
        setLogicLogs(prev => [...prev, { ts: t, level: "ERROR", message: err.message }]);
      }
    } finally {
      setLogicRunning(false);
    }
  }, [screenName, logicPhase, logicDryRun, logicRunning, agentModels, addLog]);

  // Fetch forms from DB — default F_Login
  useEffect(() => {
    addLog("INFO", "Loading forms from MongoDB...");
    fetch("/api/v1/layer3/items").then(r => r.json()).then(d => {
      if (d.success && Array.isArray(d.result)) {
        setDbScreens(d.result);
        const forms = d.result.filter((s: any) => s.type === "form" || (!s.type && s.name.startsWith("F")));
        const defaultForm = forms.find((f: any) => f.name === "F_Login") || forms[0];
        if (defaultForm) setScreenName(defaultForm.name);
        addLog("SUCCESS", `Loaded ${d.result.length} items (${forms.length} forms) — default: ${defaultForm?.name ?? "-"}`);
      }
    }).catch(err => addLog("ERROR", `DB: ${err.message}`));
  }, []);

  // Fetch queries list from MongoDB queries_v2
  useEffect(() => {
    addLog("INFO", "Loading queries from MongoDB...");
    fetch("/api/v1/layer4/queries").then(r => r.json()).then(d => {
      if (d.success && Array.isArray(d.queries)) {
        setDbQueries(d.queries);
        if (d.queries.length > 0) setQueryName(d.queries[0].name);
        addLog("SUCCESS", `Loaded ${d.queries.length} queries (queries_v2)`);
      }
    }).catch(err => addLog("WARN", `Queries: ${err.message}`));
  }, []);

  // Fetch initial token stats
  useEffect(() => {
    fetch("/api/v1/layer5/run-agent", { method: "POST", body: JSON.stringify({ agent: "repo", form_name: "INIT", dry_run: true }) })
      .then(r => r.json())
      .then(d => { if (d.token_stats) setTokenStats(d.token_stats); })
      .catch(() => { });
  }, []);

  // Resize
  useEffect(() => {
    const move = (e: MouseEvent) => { if (!isResizing.current) return; const w = document.body.clientWidth - e.clientX; if (w > 280 && w < document.body.clientWidth * 0.6) setSidebarWidth(w); };
    const up = () => { isResizing.current = false; };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
    return () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
  }, []);

  // Form list for combobox
  const formList = useMemo(() => {
    return dbScreens.filter(s => s.type === "form" || (!s.type && s.name.startsWith("F")));
  }, [dbScreens]);

  // Auto-reset selected macro/module target if it is not in the filtered type list
  useEffect(() => {
    if (!macroModuleName) return;
    const exists = dbScreens.some(s => s.name === macroModuleName && (mappingType === "all" ? (s.type === "macro" || s.type === "module") : s.type === mappingType));
    if (!exists) {
      setMacroModuleName("");
    }
  }, [mappingType, dbScreens, macroModuleName]);

  // Macro & Module list for combobox
  const macroModuleList = useMemo(() => {
    return dbScreens.filter(s => {
      if (mappingType === "all") return s.type === "macro" || s.type === "module";
      return s.type === mappingType;
    });
  }, [dbScreens, mappingType]);

  // Left sidebar state
  const [taskSidebarCollapsed, setTaskSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
    forms: false,
    reports: false,
    modules: false,
    macros: false,
  });
  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => ({ ...prev, [group]: !prev[group] }));
  };

  // ── Search helpers ────────────────────────────────────────────────────
  // Normalize fullwidth ↔ halfwidth (for Japanese input) + lowercase
  const normalizeStr = (s: string): string =>
    s.normalize("NFKC").toLowerCase();

  // Fuzzy: every char in query appears in order in target
  const fuzzyMatch = (target: string, query: string): boolean => {
    if (!query) return true;
    const t = normalizeStr(target);
    const q = normalizeStr(query);
    // First try simple substring (fastest, covers most cases)
    if (t.includes(q)) return true;
    // Fuzzy: all chars of q appear in order in t
    let ti = 0;
    for (let qi = 0; qi < q.length; qi++) {
      const found = t.indexOf(q[qi], ti);
      if (found === -1) return false;
      ti = found + 1;
    }
    return true;
  };

  const filteredSidebarItems = useMemo(() => {
    if (!searchQuery.trim()) return dbScreens;
    return dbScreens.filter(s => fuzzyMatch(s.name, searchQuery));
  }, [dbScreens, searchQuery]);

  // Counts per group (from full list, not filtered)
  const groupCounts = useMemo(() => {
    const forms   = dbScreens.filter(s => (s.type === 'form' && !s.name.toUpperCase().startsWith('R')) || (!s.type && s.name.toUpperCase().startsWith('F'))).length;
    const reports = dbScreens.filter(s => s.type === 'report' || (['form', 'report', undefined].includes(s.type) && s.name.toUpperCase().startsWith('R'))).length;
    const modules = dbScreens.filter(s => s.type === 'module').length;
    const macros  = dbScreens.filter(s => s.type === 'macro').length;
    return { forms, reports, modules, macros };
  }, [dbScreens]);

  // Run agent — moi agent doc lap, khong phu thuoc nhau
  const runAgent = useCallback(async (agentKey: string) => {
    const isRepo = agentKey === "repo";
    const isMapping = agentKey === "mapping";
    const inputTarget = isMapping ? (macroModuleName || "ALL") : (screenName || (isRepo ? queryName : ""));

    if (!isMapping && !inputTarget) {
      addLog("WARN", `[${agentKey}] Chưa chọn mục tiêu (Form/Query). Hãy chọn từ danh sách.`);
      return;
    }

    // Logic agent → dùng SSE stream qua run-logic, show tab Logic
    if (agentKey === "logic") {
      runLogicAgent();
      return;
    }

    setAgentStatuses(prev => ({ ...prev, [agentKey]: { status: "running" } }));
    const model = agentModels[agentKey] || AGENTS.find(a => a.key === agentKey)?.defaultModel || "";
    addLog("INFO", `[${agentKey}] input=${inputTarget} model=${model}`, agentKey);
    if (agentKey === "test") addLog("INFO", `[test] scope=${testAgentFilter}`, agentKey);
    setRightTab("logs");
    const start = Date.now();
    try {
      const res = await fetch("/api/v1/layer5/run-agent", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent: agentKey,
          form_name: isMapping ? (macroModuleName || "ALL") : screenName,
          model,
          ...(agentKey === "test" && testAgentFilter !== "all" ? { test_agents: [testAgentFilter] } : {}),
          ...(isRepo && queryName ? { query_name: queryName } : {}),
        }),
      });
      const data = await res.json();
      const duration = Date.now() - start;
      const tests = data.tests;
      if (tests?.ran) {
        setTestResult({
          agent: agentKey,
          formName: screenName,
          timestamp: new Date().toLocaleString("vi-VN", { hour12: false }),
          duration,
          ran: Boolean(tests.ran),
          success: Boolean(tests.success),
          errors: tests.errors || "",
          output: tests.output || "",
          filter: tests.filter || "",
          project: tests.project || "",
          cases: Array.isArray(tests.cases) ? tests.cases : [],
        });
        setRightTab("tests");
      }
      if (data.success) {
        const files = data.files || [];
        const copiedCount = data.copied ?? 0;
        const build = data.build;
        if (data.token_stats) setTokenStats(data.token_stats);
        setAgentStatuses(prev => ({ ...prev, [agentKey]: { status: "success", files, duration } }));
        addLog("SUCCESS", `✅ ${agentKey}: ${files.length} file(s) in ${(duration / 1000).toFixed(1)}s — ${copiedCount} copied to source`, agentKey);
        files.forEach((f: any) => {
          const dest = f.dest ? ` → source/vba_brain/${f.dest}` : "";
          const icon = f.copied ? "📂" : "📄";
          addLog("INFO", `  ${icon} ${f.path}${dest}`, agentKey);
        });
        // Build result
        if (build?.ran) {
          if (build.success) {
            addLog("SUCCESS", `  🔨 dotnet build OK (${build.iterations} attempt${build.iterations > 1 ? "s" : ""})`, agentKey);
          } else {
            addLog("ERROR", `  🔨 dotnet build FAILED after ${build.iterations} AI fix attempt(s)`, agentKey);
            const lastErr = build.log?.[build.log.length - 1]?.errors;
            if (lastErr) addLog("INFO", `  ${lastErr.slice(0, 300)}`, agentKey);
          }
        }
        if (tests?.ran) {
          if (tests.success) {
            addLog("SUCCESS", `  Test PASS: dotnet test ${tests.filter ? `--filter "${tests.filter}"` : ""}`, agentKey);
          } else {
            addLog("ERROR", `  Test FAIL: ${tests.errors || "See Tests tab for details"}`, agentKey);
          }
        }
        const review = data.graphview_review;
        if (agentKey === "graphview" && review) {
          const s = review.summary || {};
          const level = review.status === "PASS" ? "SUCCESS" : "ERROR";
          addLog(level, `GraphView Review: ${review.status} - ok=${s.ok ?? 0}, missing=${s.missing ?? 0}, mismatch=${s.mismatch ?? 0}, extra=${s.extra ?? 0}`, agentKey);
          if (review.status !== "PASS") {
            (review.issues || []).slice(0, 20).forEach((issue: any, idx: number) => {
              const fromTo = issue.source || issue.target ? ` [${issue.source ?? "?"} -> ${issue.target ?? "?"}]` : "";
              addLog("ERROR", `  ${idx + 1}. ${issue.rule || issue.status}: ${issue.message || "GraphView issue"}${fromTo}`, agentKey);
            });
            if ((review.issues || []).length > 20) {
              addLog("WARN", `  ... còn ${(review.issues || []).length - 20} lỗi khác, xem ${review.review_path}`, agentKey);
            }
          }
        }
        if (agentKey === "graphview" && Array.isArray(data.mongo_saved)) {
          data.mongo_saved.forEach((saved: any) => {
            addLog("INFO", `Mongo agent graphview: ${saved.upserted ? "inserted" : "updated"} ${saved.file_name}`, agentKey);
          });
        }
      } else {
        setAgentStatuses(prev => ({ ...prev, [agentKey]: { status: "error", message: data.error, duration } }));
        addLog("ERROR", `❌ ${agentKey}: ${data.error}`, agentKey);
        if (tests?.ran) {
          addLog("ERROR", "  Test output is available in the Tests tab", agentKey);
        }
      }

    } catch (err: any) {
      setAgentStatuses(prev => ({ ...prev, [agentKey]: { status: "error", message: err.message } }));
      addLog("ERROR", `${agentKey}: ${err.message}`, agentKey);
    }
  }, [screenName, queryName, agentModels, testAgentFilter, addLog, runLogicAgent, macroModuleName]);

  // Run full pipeline
  const runPipeline = useCallback(async () => {
    addLog("INFO", `══════ PIPELINE START: ${screenName} ══════`);
    for (const key of PIPELINE_ORDER) {
      await runAgent(key);
    }
    addLog("SUCCESS", `══════ PIPELINE COMPLETE ══════`);
  }, [screenName, runAgent, addLog]);

  // View files
  const viewFiles = useCallback(async (agentKey: string, type: "inputs" | "outputs") => {
    try {
      const res = await fetch(`/api/v1/layer5/files?agent=${agentKey}&type=${type}&form=${screenName}`);
      const data = await res.json();
      setPreviewContent({
        title: `${agentKey}/${type}/${screenName}`,
        content: data.success ? JSON.stringify(data.files, null, 2) : `No files.\n${data.error || ""}`,
      });
      setRightTab("preview");
    } catch { setPreviewContent({ title: `${agentKey}/${type}`, content: "Failed to load" }); setRightTab("preview"); }
  }, [screenName]);

  // Reset on form change
  useEffect(() => {
    const init: Record<string, AgentRunStatus> = {};
    AGENTS.forEach(a => { init[a.key] = { status: "idle" }; });
    setAgentStatuses(init);
    if (screenName) addLog("INFO", `Selected form: ${screenName}`);
  }, [screenName]);

  // ── Detect active mode based on selected item type ──
  // forcedItemType set by sidebar click to disambiguate (e.g. form with R prefix vs real report)
  const [forcedItemType, setForcedItemType] = useState<string | null>(null);

  const selectedItemType = useMemo(() => {
    if (forcedItemType) return forcedItemType;
    const item = dbScreens.find(s => s.name === screenName);
    if (item?.type === "report") return "report";
    if (item?.type === "macro")  return "macro";
    if (item?.type === "module") return "module";
    if (item?.type === "form")   return screenName.toUpperCase().startsWith("R") ? "report" : "form";
    // no type field — fallback by name
    if (screenName.toUpperCase().startsWith("R")) return "report";
    return "form";
  }, [dbScreens, screenName, forcedItemType]);

  // forcedItemType is set atomically with setScreenName in sidebar handlers, no need to reset

  const isMacroModuleMode = selectedItemType === "macro" || selectedItemType === "module";
  const isReportMode      = selectedItemType === "report";

  // ── ReactFlow Nodes — filtered by mode ───────
  const rfNodes: Node[] = useMemo(() => {
    // Which agents to show
    let visibleKeys: string[];
    let posMap: Record<string, { x: number; y: number }>;

    if (isMacroModuleMode) {
      visibleKeys = ["mapping", "repo"];
      posMap = NODE_POSITIONS_MACRO;
    } else if (isReportMode) {
      // Report: same pipeline but Agent UI → Agent Report
      visibleKeys = ["repo", "service", "logic", "report", "graphview", "test"];
      posMap = NODE_POSITIONS_REPORT;
    } else {
      visibleKeys = ["repo", "service", "logic", "ui", "graphview", "test"];
      posMap = NODE_POSITIONS_FORM;
    }

    return AGENTS
      .filter(agent => visibleKeys.includes(agent.key))
      .map(agent => {
        const isRepo    = agent.key === "repo";
        const isMapping = agent.key === "mapping";

        const selectedInput = isMacroModuleMode
          ? (screenName || "ALL")
          : (screenName || (isRepo ? queryName : ""));

        const isRunnable = isMacroModuleMode ? !!screenName : !!selectedInput;
        const inputLabel = isMacroModuleMode
          ? (selectedItemType === "macro" ? "Macro" : "Module")
          : isReportMode ? "Report"
          : (screenName ? "Form" : (isRepo ? "Query" : "Form"));

        return {
          id: agent.key,
          type: "l5AgentNode",
          position: posMap[agent.key] ?? { x: 0, y: 0 },
          data: {
            ...agent,
            agentKey: agent.key,
            status:   agentStatuses[agent.key]?.status || "idle",
            files:    agentStatuses[agent.key]?.files,
            duration: agentStatuses[agent.key]?.duration,
            errorMsg: agentStatuses[agent.key]?.message,
            onRun:        () => runAgent(agent.key),
            onViewInput:  () => viewFiles(agent.key, "inputs"),
            onViewOutput: () => viewFiles(agent.key, "outputs"),
            isRunnable,
            selectedInput,
            inputLabel,
            currentModel: agentModels[agent.key] || agent.defaultModel,
            modelList,
            onModelChange: (model: string) => setAgentModels(prev => ({ ...prev, [agent.key]: model })),
            macroModuleName: screenName,
            mappingType,
            macroModuleList,
          },
        };
      });
  }, [agentStatuses, screenName, queryName, isMacroModuleMode, isReportMode, selectedItemType, runAgent, viewFiles, agentModels, modelList, mappingType, macroModuleList]);

  const rfEdges: Edge[] = useMemo(() => {
    const edgeStyle = (src: string) => {
      const st = agentStatuses[src]?.status;
      const c  = AGENTS.find(a => a.key === src);
      return { stroke: st === "success" ? (c?.color || "#3b82f6") : "var(--border-color)", strokeWidth: 2 };
    };
    const isDone = (k: string) => agentStatuses[k]?.status === "success";

    if (isMacroModuleMode) {
      return [
        { id: "e-mapping-repo", source: "mapping", sourceHandle: "right", target: "repo", targetHandle: "left", animated: isDone("mapping"), style: edgeStyle("mapping") },
      ];
    }

    // The 4th node in the pipeline is "ui" for form, "report" for report
    const lastRowKey = isReportMode ? "report" : "ui";

    return [
      { id: "e-repo-service",  source: "repo",        sourceHandle: "right",  target: "service",     targetHandle: "left", animated: isDone("repo"),        style: edgeStyle("repo") },
      { id: "e-service-logic", source: "service",     sourceHandle: "right",  target: "logic",       targetHandle: "left", animated: isDone("service"),     style: edgeStyle("service") },
      { id: "e-logic-last",    source: "logic",       sourceHandle: "right",  target: lastRowKey,    targetHandle: "left", animated: isDone("logic"),       style: edgeStyle("logic") },
      { id: "e-repo-gv",       source: "repo",        sourceHandle: "bottom", target: "graphview",   targetHandle: "top",  animated: isDone("repo"),        style: { ...edgeStyle("repo"),        strokeDasharray: "5 3" }, type: "smoothstep" },
      { id: "e-service-gv",    source: "service",     sourceHandle: "bottom", target: "graphview",   targetHandle: "top",  animated: isDone("service"),     style: { ...edgeStyle("service"),     strokeDasharray: "5 3" }, type: "smoothstep" },
      { id: "e-logic-gv",      source: "logic",       sourceHandle: "bottom", target: "graphview",   targetHandle: "top",  animated: isDone("logic"),       style: { ...edgeStyle("logic"),       strokeDasharray: "5 3" }, type: "smoothstep" },
      { id: "e-last-gv",       source: lastRowKey,    sourceHandle: "bottom", target: "graphview",   targetHandle: "top",  animated: isDone(lastRowKey),    style: { ...edgeStyle(lastRowKey),    strokeDasharray: "5 3" }, type: "smoothstep" },
      { id: "e-gv-test",       source: "graphview",   sourceHandle: "bottom", target: "test",        targetHandle: "top",  animated: isDone("graphview"),   style: edgeStyle("graphview") },
    ];
  }, [agentStatuses, isMacroModuleMode, isReportMode]);

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges);

  useEffect(() => {
    // When mode changes (form ↔ macro/module), node set changes entirely — replace all.
    // When only data changes (status, model…), preserve ReactFlow positions.
    setNodes(prevNodes => {
      if (!prevNodes || prevNodes.length === 0) return rfNodes;
      const prevIds = new Set(prevNodes.map(n => n.id));
      const newIds  = new Set(rfNodes.map(n => n.id));
      // If node set changed (mode switch), replace entirely so fitView can re-run
      const setsEqual = prevIds.size === newIds.size && [...prevIds].every(id => newIds.has(id));
      if (!setsEqual) return rfNodes;
      // Same set — just update data, preserve position
      return prevNodes.map(prevNode => {
        const matching = rfNodes.find(n => n.id === prevNode.id);
        if (!matching) return prevNode;
        return { ...prevNode, data: matching.data };
      });
    });
  }, [rfNodes, setNodes]);

  useEffect(() => {
    setEdges(rfEdges);
  }, [rfEdges, setEdges]);

  const pipelineProgress = useMemo(() => {
    const total = PIPELINE_ORDER.length;
    const done = PIPELINE_ORDER.filter(k => agentStatuses[k]?.status === "success").length;
    return { done, total, pct: total > 0 ? Math.round((done / total) * 100) : 0 };
  }, [agentStatuses]);

  const getLogColor = (level: string) => level === "ERROR" ? "#ef4444" : level === "SUCCESS" ? "#10b981" : level === "WARN" ? "#f59e0b" : "#60a5fa";
  const getAgentColor = (agent?: string) => agent ? AGENTS.find(a => a.key === agent)?.color : undefined;
  const testSummary = useMemo(() => {
    const cases = testResult?.cases || [];
    const passed = cases.filter(c => c.outcome === "Passed").length;
    const failed = cases.filter(c => c.outcome === "Failed").length;
    const skipped = cases.filter(c => c.outcome === "NotExecuted" || c.outcome === "Skipped").length;
    return { total: cases.length, passed, failed, skipped };
  }, [testResult]);
  const getTestOutcomeColor = (outcome: string) => outcome === "Passed" ? "#10b981" : outcome === "Failed" ? "#ef4444" : "#f59e0b";

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <Header />

      <main className="layout-content">
        {/* ── Left Task Sidebar ── */}
        <div className="task-sidebar" style={{
          width: taskSidebarCollapsed ? 40 : 240,
          flexShrink: 0,
          transition: 'width 0.22s cubic-bezier(.4,0,.2,1)',
          overflow: 'hidden',
          position: 'relative',
        }}>
          {/* Header row */}
          <div style={{ display: 'flex', alignItems: 'center', padding: taskSidebarCollapsed ? '12px 8px' : '10px 12px', borderBottom: '1px solid var(--border-color)', gap: 6, flexShrink: 0, minHeight: 42 }}>
            {!taskSidebarCollapsed && (
              <span style={{ color: "var(--text-muted)", fontSize: '12px', fontWeight: 600, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden' }}>
                <strong style={{ color: "var(--text-main)" }}>L5</strong> Items
              </span>
            )}
            <button onClick={() => setTaskSidebarCollapsed(v => !v)}
              title={taskSidebarCollapsed ? 'Mở sidebar' : 'Thu gọn sidebar'}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: "var(--text-muted)", display: 'flex', alignItems: 'center', padding: 2, borderRadius: 4, flexShrink: 0 }}>
              {taskSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
            </button>
          </div>

          {/* Collapsed icon strip */}
          {taskSidebarCollapsed && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '6px 0', gap: 2 }}>
              {dbScreens.filter(s => s.type === 'form').slice(0, 8).map((item, idx) => (
                <div key={idx} title={item.name}
                  onClick={() => { setScreenName(item.name); setTaskSidebarCollapsed(false); }}
                  style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6, cursor: 'pointer', background: screenName === item.name ? 'rgba(168,85,247,0.2)' : 'transparent' }}>
                  <DatabaseZap size={13} style={{ color: screenName === item.name ? '#a855f7' : "var(--text-muted)" }} />
                </div>
              ))}
            </div>
          )}

          {/* Full sidebar content */}
          {!taskSidebarCollapsed && (
            <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column' }}>
              {/* Run Pipeline Controls inside Sidebar */}
              <div style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: 10, background: "rgba(168,85,247,0.03)" }}>
                <button onClick={runPipeline} disabled={!screenName}
                  style={{ 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center", 
                    gap: 6, 
                    padding: "8px 14px", 
                    borderRadius: 6, 
                    border: "none", 
                    background: screenName ? "linear-gradient(135deg, #a855f7, #6366f1)" : "var(--border-color)", 
                    color: screenName ? "#fff" : "var(--text-muted)", 
                    fontSize: 12, 
                    fontWeight: 700, 
                    cursor: screenName ? "pointer" : "not-allowed",
                    boxShadow: screenName ? "0 4px 12px rgba(168,85,247,0.2)" : "none",
                    transition: "all 0.2s"
                  }}>
                  <Play size={14} /> Run Pipeline
                </button>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11 }}>
                  <span style={{ color: "var(--text-muted)" }}>Progress: {pipelineProgress.done}/{pipelineProgress.total}</span>
                  <span style={{ color: "#a855f7", fontWeight: 600 }}>{pipelineProgress.pct}%</span>
                </div>
                <div style={{ width: "100%", height: 6, background: "#1f2937", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 4, background: "linear-gradient(90deg, #a855f7, #3b82f6)", width: `${pipelineProgress.pct}%`, transition: "width 0.4s" }} />
                </div>
              </div>

              {/* Search */}
              <div className="task-search-container">
                <div style={{ position: 'relative' }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input type="text" className="task-search-input" placeholder="Tìm theo tên..."
                    value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
                </div>
              </div>

              {/* Forms group */}
              <div className="task-group-title" onClick={() => toggleGroup('forms')}>
                {collapsedGroups.forms ? <ChevronRight size={14} /> : <ChevronDown size={14} />} 🖥️ Forms
                <span style={{ marginLeft: 'auto', fontSize: 10, background: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 10, padding: '1px 6px', fontWeight: 700 }}>{groupCounts.forms}</span>
              </div>
              {!collapsedGroups.forms && filteredSidebarItems.filter(s =>
                (s.type === 'form' && !s.name.toUpperCase().startsWith('R')) ||
                (!s.type && s.name.toUpperCase().startsWith('F'))
              ).map((item, idx) => (
                <div key={`form-${idx}`}
                  className={`task-item ${screenName === item.name ? 'active' : ''}`}
                  onClick={() => { setScreenName(item.name); setForcedItemType('form'); }}>
                  <DatabaseZap size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              {/* Reports group */}
              <div className="task-group-title" style={{ marginTop: 8 }} onClick={() => toggleGroup('reports')}>
                {collapsedGroups.reports ? <ChevronRight size={14} /> : <ChevronDown size={14} />} 📊 Reports
                <span style={{ marginLeft: 'auto', fontSize: 10, background: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 10, padding: '1px 6px', fontWeight: 700 }}>{groupCounts.reports}</span>
              </div>
              {!collapsedGroups.reports && filteredSidebarItems.filter(s =>
                s.type === 'report' ||
                (['form', 'report', undefined].includes(s.type) && s.name.toUpperCase().startsWith('R'))
              ).map((item, idx) => (
                <div key={`report-${idx}`}
                  className={`task-item ${screenName === item.name ? 'active' : ''}`}
                  onClick={() => { setScreenName(item.name); setForcedItemType('report'); setMappingType('all'); }}>
                  <DatabaseZap size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              {/* Modules group */}
              <div className="task-group-title" style={{ marginTop: 8 }} onClick={() => toggleGroup('modules')}>
                {collapsedGroups.modules ? <ChevronRight size={14} /> : <ChevronDown size={14} />} 📦 Modules
                <span style={{ marginLeft: 'auto', fontSize: 10, background: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 10, padding: '1px 6px', fontWeight: 700 }}>{groupCounts.modules}</span>
              </div>
              {!collapsedGroups.modules && filteredSidebarItems.filter(s => s.type === 'module').map((item, idx) => (
                <div key={`mod-${idx}`}
                  className={`task-item ${screenName === item.name ? 'active' : ''}`}
                  onClick={() => { setScreenName(item.name); setMacroModuleName(item.name); setMappingType('module'); setForcedItemType('module'); }}>
                  <Terminal size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              {/* Macros group */}
              <div className="task-group-title" style={{ marginTop: 8 }} onClick={() => toggleGroup('macros')}>
                {collapsedGroups.macros ? <ChevronRight size={14} /> : <ChevronDown size={14} />} ⚙️ Macros
                <span style={{ marginLeft: 'auto', fontSize: 10, background: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 10, padding: '1px 6px', fontWeight: 700 }}>{groupCounts.macros}</span>
              </div>
              {!collapsedGroups.macros && filteredSidebarItems.filter(s => s.type === 'macro').map((item, idx) => (
                <div key={`mac-${idx}`}
                  className={`task-item ${screenName === item.name ? 'active' : ''}`}
                  onClick={() => { setScreenName(item.name); setMacroModuleName(item.name); setMappingType('macro'); setForcedItemType('macro'); }}>
                  <Terminal size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Center: ReactFlow Workflow ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <ReactFlow
              nodes={nodes} edges={edges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              minZoom={0.3} maxZoom={1.5}
              proOptions={{ hideAttribution: true }}
              onInit={(reactFlowInstance) => {
                setTimeout(() => {
                  reactFlowInstance.fitView({ padding: 0.3 });
                }, 50);
              }}
            >
              <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--border-color)" />
              <Controls style={{ background: "var(--bg-panel)", fill: "var(--text-main)" }} />
            </ReactFlow>
          </div>
        </div>

        {/* ── Right Sidebar: Logs + Preview ── */}
        <div className="terminal-sidebar" style={{ width: terminalCollapsed ? 40 : sidebarWidth, overflow: "hidden", transition: "width 0.22s" }}>
          {!terminalCollapsed && <div className="sidebar-resizer" onMouseDown={() => { isResizing.current = true; }} />}
          <div style={{ display: "flex", borderBottom: "1px solid var(--border-color)", backgroundColor: "#151822" }}>
            <button 
              onClick={() => setTerminalCollapsed(v => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 12px', display: 'flex', alignItems: 'center', height: 42, flexShrink: 0 }}
            >
              {terminalCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
            </button>
            <div style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "logs" ? "#10b981" : "var(--text-muted)", borderBottom: rightTab === "logs" ? "2px solid #10b981" : "2px solid transparent" }}
              onClick={() => setRightTab("logs")}>
              <Settings2 size={13} /> Pipeline Log
            </div>
            <div style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "preview" ? "#f59e0b" : "var(--text-muted)", borderBottom: rightTab === "preview" ? "2px solid #f59e0b" : "2px solid transparent" }}
              onClick={() => setRightTab("preview")}>
              <Eye size={13} /> Preview
            </div>
            <div style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "tests" ? "#10b981" : "var(--text-muted)", borderBottom: rightTab === "tests" ? "2px solid #10b981" : "2px solid transparent" }}
              onClick={() => setRightTab("tests")}>
              <BarChart3 size={13} /> Tests
            </div>
            <div style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "tokens" ? "#a855f7" : "var(--text-muted)", borderBottom: rightTab === "tokens" ? "2px solid #a855f7" : "2px solid transparent" }}
              onClick={() => setRightTab("tokens")}>
              <BarChart3 size={13} /> Tokens
            </div>
            <div style={{ padding: "10px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 5, color: rightTab === "logic" ? "#8b5cf6" : "var(--text-muted)", borderBottom: rightTab === "logic" ? "2px solid #8b5cf6" : "2px solid transparent" }}
              onClick={() => setRightTab("logic")}>
              <Brain size={13} /> Logic
              {logicRunning && <Loader2 size={10} style={{ animation: "spin 1s linear infinite" }} />}
              {!logicRunning && logicSummary && (
                <span style={{ fontSize: 9, padding: "1px 3px", borderRadius: 3, background: logicSummary.compile_ok ? "#10b98122" : "#f59e0b22", color: logicSummary.compile_ok ? "#10b981" : "#f59e0b" }}>
                  {logicSummary.compile_ok ? "🟢" : "🟡"}
                </span>
              )}
            </div>
          </div>

          {rightTab === "logs" && (
            <div className="terminal-content" style={{ overflowY: "auto", flex: 1, padding: 0 }}>
              <div style={{ padding: 16 }}>
                {logs.map((log, i) => (
                  <div key={i} className="log-line">
                    <span className="log-time">[{log.time}]</span>
                    {log.agent && <span style={{ color: getAgentColor(log.agent), fontWeight: 600, fontSize: 11 }}>[{log.agent}]</span>}
                    <span style={{ color: getLogColor(log.level), fontWeight: "bold" }}> [{log.level}]</span>
                    <span style={{ marginLeft: 6, color: "var(--text-main)" }}>{log.message}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}
          {rightTab === "preview" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16, overflow: "hidden" }}>
              {previewContent ? (
                <>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b", marginBottom: 8 }}>{previewContent.title}</div>
                  <textarea readOnly value={previewContent.content}
                    style={{ flex: 1, fontFamily: "monospace", fontSize: 12, color: "#fbbf24", background: "#291c0a", padding: 16, borderRadius: 6, border: "1px solid #451a03", resize: "none", whiteSpace: "pre", overflowX: "auto" }} />
                </>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", marginTop: 40 }}>
                  <Eye size={32} style={{ margin: "0 auto 12px", opacity: 0.5 }} /><br />
                  Click 👁 or 📄 on a node to preview files
                </div>
              )}
            </div>
          )}

          {rightTab === "tests" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16, overflow: "hidden", gap: 12 }}>
              {testResult ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: testResult.success ? "#10b981" : "#ef4444" }}>
                        {testResult.success ? "PASS" : "FAIL"} - dotnet test
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>
                        {testResult.formName} - {(testResult.duration / 1000).toFixed(1)}s - {testResult.timestamp}
                      </div>
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: testResult.success ? "#86efac" : "#fca5a5", background: testResult.success ? "#052e1b" : "#3f1111", border: `1px solid ${testResult.success ? "#14532d" : "#7f1d1d"}`, borderRadius: 999, padding: "4px 10px", whiteSpace: "nowrap" }}>
                      {testResult.success ? "SUCCESS" : "FAILED"}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 8, fontSize: 11, color: "#d1d5db" }}>
                    <div><span style={{ color: "var(--text-muted)" }}>Project:</span> {testResult.project || "vba_brain.Tests"}</div>
                    <div><span style={{ color: "var(--text-muted)" }}>Filter:</span> {testResult.filter || "all tests"}</div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                    {[
                      ["Total", testSummary.total, "#d1d5db"],
                      ["Passed", testSummary.passed, "#10b981"],
                      ["Failed", testSummary.failed, "#ef4444"],
                      ["Skipped", testSummary.skipped, "#f59e0b"],
                    ].map(([label, value, color]) => (
                      <div key={String(label)} style={{ background: "var(--bg-dark)", border: "1px solid #1f2937", borderRadius: 6, padding: "8px 10px" }}>
                        <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>{label}</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: String(color) }}>{String(value)}</div>
                      </div>
                    ))}
                  </div>

                  <div style={{ flex: 1, minHeight: 220, overflow: "auto", border: "1px solid #1f2937", borderRadius: 6, background: "#0b1220" }}>
                    {testResult.cases.length > 0 ? (
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                        <thead style={{ position: "sticky", top: 0, background: "var(--bg-dark)", zIndex: 1 }}>
                          <tr style={{ textAlign: "left" }}>
                            <th style={{ padding: "8px 10px", color: "var(--text-muted)", width: 74 }}>Status</th>
                            <th style={{ padding: "8px 10px", color: "var(--text-muted)" }}>Test case</th>
                            <th style={{ padding: "8px 10px", color: "var(--text-muted)", width: 88 }}>Duration</th>
                          </tr>
                        </thead>
                        <tbody>
                          {testResult.cases.map((testCase, idx) => (
                            <tr key={`${testCase.className}-${testCase.name}-${idx}`} style={{ borderTop: "1px solid #1f2937", verticalAlign: "top" }}>
                              <td style={{ padding: "8px 10px" }}>
                                <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", minWidth: 58, padding: "2px 7px", borderRadius: 999, fontSize: 10, fontWeight: 800, color: getTestOutcomeColor(testCase.outcome), background: testCase.outcome === "Passed" ? "#052e1b" : testCase.outcome === "Failed" ? "#3f1111" : "#2a1d06", border: `1px solid ${testCase.outcome === "Passed" ? "#14532d" : testCase.outcome === "Failed" ? "#7f1d1d" : "#78350f"}` }}>
                                  {testCase.outcome}
                                </span>
                              </td>
                              <td style={{ padding: "8px 10px", color: "var(--text-main)" }}>
                                <div style={{ fontWeight: 700, lineHeight: 1.4, wordBreak: "break-word" }}>{testCase.name}</div>
                                {testCase.className && <div style={{ color: "var(--text-muted)", marginTop: 2, wordBreak: "break-word" }}>{testCase.className}</div>}
                                {testCase.errorMessage && (
                                  <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", color: "#fecaca", background: "#240b0b", border: "1px solid #7f1d1d", borderRadius: 4, padding: 8, fontFamily: "monospace", fontSize: 10 }}>
                                    {testCase.errorMessage}
                                  </pre>
                                )}
                                {testCase.output && (
                                  <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", color: "#d1fae5", background: "#061b14", border: "1px solid #064e3b", borderRadius: 4, padding: 8, fontFamily: "monospace", fontSize: 10 }}>
                                    {testCase.output}
                                  </pre>
                                )}
                              </td>
                              <td style={{ padding: "8px 10px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>{testCase.duration || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: 24 }}>
                        No testcase details found. Build may have failed before test execution.
                      </div>
                    )}
                  </div>

                  {testResult.errors && (
                    <>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#ef4444" }}>Errors</div>
                      <textarea readOnly value={testResult.errors}
                        style={{ minHeight: 130, fontFamily: "monospace", fontSize: 11, color: "#fecaca", background: "#240b0b", padding: 12, borderRadius: 6, border: "1px solid #7f1d1d", resize: "vertical", whiteSpace: "pre", overflowX: "auto" }} />
                    </>
                  )}

                  <details style={{ color: "var(--text-muted)", fontSize: 12 }}>
                    <summary style={{ cursor: "pointer", color: "#10b981", fontWeight: 700 }}>Raw dotnet output</summary>
                    <textarea readOnly value={testResult.output || "No dotnet test output."}
                      style={{ width: "100%", height: 120, marginTop: 8, fontFamily: "monospace", fontSize: 11, color: "#d1fae5", background: "#061b14", padding: 12, borderRadius: 6, border: "1px solid #064e3b", resize: "vertical", whiteSpace: "pre", overflowX: "auto" }} />
                  </details>
                </>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", marginTop: 40 }}>
                  <BarChart3 size={32} style={{ margin: "0 auto 12px", opacity: 0.5 }} /><br />
                  Run Agent Test to see dotnet test results
                </div>
              )}
            </div>
          )}

          {rightTab === "tokens" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16, overflowY: "auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <h3 style={{ margin: 0, fontSize: 14, color: "#a855f7", display: "flex", alignItems: "center", gap: 8 }}>
                  <BarChart3 size={16} /> AI Token Consumption
                </h3>
                <button onClick={() => window.open("/api/layer5/download-token-report")}
                  style={{ display: "flex", alignItems: "center", gap: 6, background: "#1e293b", border: "1px solid #334155", color: "#94a3b8", padding: "4px 10px", borderRadius: 4, fontSize: 11, cursor: "pointer" }}>
                  <Download size={12} /> Excel
                </button>
              </div>

              {tokenStats ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div style={{ background: "var(--bg-dark)", padding: 12, borderRadius: 8, border: "1px solid #1f2937" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>Total Tokens</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-main)" }}>{tokenStats.total_tokens.toLocaleString()}</div>
                    </div>
                    <div style={{ background: "var(--bg-dark)", padding: 12, borderRadius: 8, border: "1px solid #1f2937" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>Est. Cost (USD)</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#10b981" }}>${tokenStats.total_cost_usd.toFixed(4)}</div>
                    </div>
                  </div>

                  <div style={{ background: "var(--bg-dark)", borderRadius: 8, border: "1px solid #1f2937", overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                      <thead>
                        <tr style={{ background: "#1f2937", textAlign: "left" }}>
                          <th style={{ padding: "8px 10px", color: "var(--text-muted)" }}>Agent / Task</th>
                          <th style={{ padding: "8px 10px", color: "var(--text-muted)", textAlign: "right" }}>Tokens</th>
                          <th style={{ padding: "8px 10px", color: "var(--text-muted)", textAlign: "right" }}>Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tokenStats.records.slice().reverse().map((r, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid #1f2937" }}>
                            <td style={{ padding: "8px 10px" }}>
                              <div style={{ fontWeight: 600, color: getAgentColor(r.agent) }}>{r.agent.toUpperCase()}</div>
                              <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{r.task_type} • {r.form_name}</div>
                            </td>
                            <td style={{ padding: "8px 10px", textAlign: "right", color: "var(--text-main)" }}>
                              {r.total_tokens.toLocaleString()}
                            </td>
                            <td style={{ padding: "8px 10px", textAlign: "right", color: "#10b981" }}>
                              ${r.cost_usd.toFixed(4)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", marginTop: 40 }}>
                  <BarChart3 size={32} style={{ margin: "0 auto 12px", opacity: 0.5 }} /><br />
                  Run an agent to see token usage
                </div>
              )}
            </div>
          )}

          {/* ── Logic Console Tab ── */}
          {rightTab === "logic" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {/* Phase selector — chỉ để xem/chọn, Run thực hiện từ node */}
              <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border-color)", background: "#151822", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 700 }}>PHASE</span>
                {(["all", "ui", "service"] as LogicPhase[]).map(p => (
                  <button key={p} onClick={() => setLogicPhase(p)} style={{
                    padding: "3px 8px", borderRadius: 4, border: `1px solid ${logicPhase === p ? "#8b5cf6" : "var(--border-color)"}`,
                    background: logicPhase === p ? "#8b5cf622" : "transparent",
                    color: logicPhase === p ? "#a78bfa" : "var(--text-muted)",
                    fontSize: 11, fontWeight: 600, cursor: "pointer",
                  }}>{p.toUpperCase()}</button>
                ))}
                <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer", marginLeft: 4 }}>
                  <input type="checkbox" checked={logicDryRun} onChange={e => setLogicDryRun(e.target.checked)} style={{ accentColor: "#f59e0b" }} />
                  <span style={{ fontSize: 10, color: "#f59e0b" }}>dry-run</span>
                </label>
                <span style={{ marginLeft: "auto", fontSize: 10, color: "#4b5563", fontStyle: "italic" }}>
                  {logicRunning ? "⏳ Running..." : "Click ▶ Run on the Logic node →"}
                </span>
              </div>

              {/* Summary strip */}
              {logicSummary && (
                <div style={{ display: "flex", gap: 0, borderBottom: "1px solid var(--border-color)", background: "#0f1117" }}>
                  {[
                    { k: "DONE", v: logicSummary.done, color: "#10b981", icon: "✅" },
                    { k: "TODO", v: logicSummary.todo, color: "#f59e0b", icon: "⚠️" },
                    { k: "SKIP", v: logicSummary.skip, color: "var(--text-muted)", icon: "⏭" },
                    { k: "ERROR", v: logicSummary.error, color: "#ef4444", icon: "❌" },
                  ].map(s => (
                    <div key={s.k} style={{ flex: 1, textAlign: "center", padding: "6px 4px", borderRight: "1px solid #1f2937" }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: s.color }}>{s.v}</div>
                      <div style={{ fontSize: 9, color: s.color, opacity: 0.8 }}>{s.icon} {s.k}</div>
                    </div>
                  ))}
                  <div style={{ flex: 2, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: logicSummary.compile_ok ? "#10b981" : "#f59e0b", fontWeight: 600 }}>
                    {logicSummary.compile_ok ? "🟢 Ready" : "🟡 Review TODOs"}
                  </div>
                </div>
              )}

              {/* Log stream */}
              <div style={{ flex: 1, overflowY: "auto", padding: "8px 12px", fontFamily: "monospace", fontSize: 11, lineHeight: 1.6, background: "#0f1117" }}>
                {logicLogs.length === 0 && !logicSummary && (
                  <div style={{ color: "var(--border-color)", textAlign: "center", marginTop: 40, fontSize: 12 }}>
                    <Brain size={28} style={{ margin: "0 auto 8px", display: "block", opacity: 0.3 }} /><br />
                    Select form above → choose phase → Run Logic
                  </div>
                )}
                {logicLogs.map((log, i) => {
                  const c = log.level === "ERROR" ? "#ef4444" : log.level === "SUCCESS" ? "#10b981" : log.level === "WARN" ? "#f59e0b" : log.level === "LLM" ? "#a855f7" : "#60a5fa";
                  return (
                    <div key={i} style={{ display: "flex", gap: 6, marginBottom: 1 }}>
                      <span style={{ color: "var(--border-color)", flexShrink: 0 }}>[{log.ts}]</span>
                      <span style={{ color: c, fontWeight: 600, flexShrink: 0, minWidth: 50 }}>[{log.level}]</span>
                      <span style={{ color: "#d1d5db", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{log.message}</span>
                    </div>
                  );
                })}

                {/* Event status table */}
                {logicMethods.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 700, marginBottom: 6, letterSpacing: 1 }}>
                      EVENT STATUS — {screenName}
                      {logicPhase !== "all" && (
                        <span style={{
                          marginLeft: 6, padding: "1px 5px", borderRadius: 3, fontSize: 9,
                          background: logicPhase === "ui" ? "#ec489922" : "#3b82f622",
                          color: logicPhase === "ui" ? "#f9a8d4" : "#93c5fd"
                        }}>
                          {logicPhase.toUpperCase()} only
                        </span>
                      )}
                    </div>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10 }}>
                      <thead>
                        <tr style={{ background: "#1a1d27" }}>
                          {["EID", "Type", "Handler", "C# Method", "Status", "Note"].map(h => (
                            <th key={h} style={{ padding: "4px 6px", textAlign: "left", color: "var(--text-muted)", borderBottom: "1px solid #2e3039" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {logicMethods
                          .filter(m => logicPhase === "all" || (m.phase_type ?? "ui") === logicPhase)
                          .map((m, i) => {
                            const cs = (m.code_status ?? (m.status === "skipped" ? "SKIP" : "DONE")) as LogicCodeStatus;
                            const cfg = LOGIC_CODE_CFG[cs] ?? LOGIC_CODE_CFG.SKIP;
                            const pt = m.phase_type ?? "ui";
                            return (
                              <tr key={i}
                                onClick={() => m.code_preview && setPreviewContent({ title: m.cs_name ?? m.notes, content: m.code_preview })}
                                style={{ borderBottom: "1px solid #1a1d27", cursor: m.code_preview ? "pointer" : "default", background: "transparent" }}>
                                <td style={{ padding: "3px 6px", color: "var(--text-muted)", fontFamily: "monospace" }}>{m.event_id}</td>
                                <td style={{ padding: "3px 6px" }}>
                                  <span style={{
                                    padding: "1px 4px", borderRadius: 3, fontSize: 9, fontWeight: 700,
                                    background: pt === "ui" ? "#ec489918" : "#3b82f618",
                                    color: pt === "ui" ? "#f9a8d4" : "#93c5fd"
                                  }}>
                                    {pt.toUpperCase()}
                                  </span>
                                </td>
                                <td style={{ padding: "3px 6px", color: "var(--text-main)", maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={m.notes}>{m.notes}</td>
                                <td style={{ padding: "3px 6px", color: "#93c5fd", fontFamily: "monospace", fontSize: 9 }}>{m.cs_name ?? "—"}</td>
                                <td style={{ padding: "3px 6px" }}>
                                  <span style={{ display: "inline-flex", alignItems: "center", gap: 2, padding: "1px 5px", borderRadius: 3, fontSize: 9, fontWeight: 700, background: cfg.bg, color: cfg.color }}>
                                    {cfg.icon} {cs}
                                  </span>
                                </td>
                                <td style={{ padding: "3px 6px", color: "var(--text-muted)", fontSize: 9, fontStyle: "italic" }}>{m.note}</td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                    {logicPreview && (
                      <div style={{ marginTop: 8, fontSize: 10, color: "#60a5fa", cursor: "pointer" }}
                        onClick={() => { if (logicPreview) { setPreviewContent({ title: logicPreview.title, content: logicPreview.content }); setRightTab("preview"); } }}>
                        📄 View updated {logicPreview.title} →
                      </div>
                    )}
                  </div>
                )}
                <div ref={logicLogsEndRef} />
              </div>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
