"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { FileSpreadsheet, Search, ChevronDown, ChevronRight, Download, Settings2, Eye, DatabaseZap, Bot, Database, Cpu, Sparkles } from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
// @ts-ignore
import { ReactFlow, Controls, Background, Node, Edge, useNodesState, useEdgesState, BackgroundVariant } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { L3ExcelNode } from "../../components/nodes/L3ExcelNode";

// ── Types ──────────────────────────────────────────────────────────────────────
interface L3Item { name: string; has_bd: boolean; has_dd: boolean; type: string; }
interface NodeStatus {
  status: "idle" | "running" | "success" | "error";
  outputFile?: string; outputSizeKb?: number; errorMsg?: string; duration?: number;
  downloadUrl?: string;
}
interface OutputFile { filename: string; doc_kind: string; doc_type: string; size_kb: number; download_url: string; }
interface LogEntry { time: string; level: string; message: string; }

// ── Node positions ─────────────────────────────────────────────────────────────
const BD_NODE_POS = { x: 80, y: 60 };
const DD_NODE_POS = { x: 80, y: 320 };

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function Layer4Page() {
  const [items, setItems] = useState<L3Item[]>([]);
  const [selectedName, setSelectedName] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState({ forms: false, reports: false, modules: false, macros: false });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [bdStatus, setBdStatus] = useState<NodeStatus>({ status: "idle" });
  const [ddStatus, setDdStatus] = useState<NodeStatus>({ status: "idle" });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [outputFiles, setOutputFiles] = useState<OutputFile[]>([]);
  const [rightTab, setRightTab] = useState<"logs" | "files">("logs");
  const logsEndRef = useRef<HTMLDivElement>(null);
  const nodeTypes = useMemo(() => ({ l3ExcelNode: L3ExcelNode }), []);

  const addLog = useCallback((level: string, msg: string) => {
    const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });
    setLogs(prev => [...prev, { time, level, message: msg }]);
  }, []);

  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  // Fetch items from layer4 backend
  useEffect(() => {
    addLog("INFO", "Loading items from Layer 4 backend…");
    fetch("/api/v1/layer4/items")
      .then(r => r.json())
      .then(d => {
        if (d.success && Array.isArray(d.result)) {
          setItems(d.result);
          const first = d.result.find((i: L3Item) => i.type === "form") || d.result[0];
          if (first) setSelectedName(first.name);
          const forms   = d.result.filter((i: L3Item) => i.type === "form").length;
          const reports = d.result.filter((i: L3Item) => i.type === "report").length;
          const modules = d.result.filter((i: L3Item) => i.type === "module").length;
          const macros  = d.result.filter((i: L3Item) => i.type === "macro").length;
          const hasBd   = d.result.filter((i: L3Item) => i.has_bd).length;
          const hasDd   = d.result.filter((i: L3Item) => i.has_dd).length;
          addLog("SUCCESS", `Loaded ${d.result.length} items from Layer1 — forms:${forms} reports:${reports} modules:${modules} macros:${macros}`);
          addLog("INFO", `BD available: ${hasBd} items | DD available: ${hasDd} items`);
        } else {
          addLog("ERROR", `Failed to load items: ${d.error || "unknown error"}`);
        }
      })
      .catch(e => addLog("ERROR", `Layer3 server not running? ${e.message}`));
  }, [addLog]);

  // Fetch output files list
  const refreshOutputs = useCallback(() => {
    fetch("/api/v1/layer4/list-outputs")
      .then(r => r.json())
      .then(d => { if (d.success) setOutputFiles(d.files || []); })
      .catch(() => {});
  }, []);

  useEffect(() => { refreshOutputs(); }, [refreshOutputs]);

  // Reset node statuses on item change
  useEffect(() => {
    setBdStatus({ status: "idle" });
    setDdStatus({ status: "idle" });
    if (selectedName) addLog("INFO", `Selected: ${selectedName}`);
  }, [selectedName, addLog]);

  const selectedItem = useMemo(() => items.find(i => i.name === selectedName), [items, selectedName]);

  // Generate BD Excel
  const handleGenBd = useCallback(async () => {
    if (!selectedName) return;
    setBdStatus({ status: "running" });
    addLog("INFO", `[BD] Generating Excel for ${selectedName}…`);
    const start = Date.now();
    try {
      const res = await fetch("/api/v1/layer4/gen-bd", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ screenName: selectedName, type: "auto" }),
      });
      const data = await res.json();
      const duration = Date.now() - start;
      if (data.success) {
        setBdStatus({ status: "success", outputFile: data.filename, outputSizeKb: data.size_kb, duration, downloadUrl: data.download_url });
        addLog("SUCCESS", `[BD] ✅ ${data.filename} (${data.size_kb} KB, ${data.duration_sec}s)`);
        refreshOutputs();
      } else {
        setBdStatus({ status: "error", errorMsg: data.error || "Unknown error" });
        addLog("ERROR", `[BD] ❌ ${data.error}`);
      }
    } catch (e: any) {
      setBdStatus({ status: "error", errorMsg: e.message });
      addLog("ERROR", `[BD] ❌ ${e.message}`);
    }
  }, [selectedName, addLog, refreshOutputs]);

  // Generate DD Excel
  const handleGenDd = useCallback(async () => {
    if (!selectedName) return;
    setDdStatus({ status: "running" });
    addLog("INFO", `[DD] Generating Excel for ${selectedName}…`);
    const start = Date.now();
    try {
      const res = await fetch("/api/v1/layer4/gen-dd", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ screenName: selectedName, type: "auto" }),
      });
      const data = await res.json();
      const duration = Date.now() - start;
      if (data.success) {
        setDdStatus({ status: "success", outputFile: data.filename, outputSizeKb: data.size_kb, duration, downloadUrl: data.download_url });
        addLog("SUCCESS", `[DD] ✅ ${data.filename} (${data.size_kb} KB, ${data.duration_sec}s)`);
        refreshOutputs();
      } else {
        setDdStatus({ status: "error", errorMsg: data.error || "Unknown error" });
        addLog("ERROR", `[DD] ❌ ${data.error}`);
      }
    } catch (e: any) {
      setDdStatus({ status: "error", errorMsg: e.message });
      addLog("ERROR", `[DD] ❌ ${e.message}`);
    }
  }, [selectedName, addLog, refreshOutputs]);

  // Generate both BD + DD (or only DD for modules/macros)
  const handleGenAll = useCallback(async () => {
    if (!selectedName) return;
    const isModuleOrMacro = selectedItem?.type === "module" || selectedItem?.type === "macro";
    if (isModuleOrMacro) {
      await handleGenDd();
    } else {
      await handleGenBd();
      await handleGenDd();
    }
  }, [selectedName, selectedItem, handleGenBd, handleGenDd]);

  // Download helper
  const handleDownload = useCallback((downloadUrl: string, filename: string) => {
    // Convert backend URL to frontend proxy URL
    // downloadUrl from backend: /api/l3/download/BD/screen/...
    // We need: /api/layer4/download/BD/screen/...
    const proxyUrl = downloadUrl.replace("/api/l3/download/", "/api/v1/layer4/download/");
    const a = document.createElement("a");
    a.href = proxyUrl;
    a.download = filename;
    a.click();
  }, []);

  // Search filter
  const normalizeStr = (s: string) => s.normalize("NFKC").toLowerCase();
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = normalizeStr(searchQuery);
    return items.filter(i => normalizeStr(i.name).includes(q));
  }, [items, searchQuery]);

  const groupCounts = useMemo(() => ({
    forms:   items.filter(i => i.type === "form").length,
    reports: items.filter(i => i.type === "report").length,
    modules: items.filter(i => i.type === "module").length,
    macros:  items.filter(i => i.type === "macro").length,
  }), [items]);

  // ReactFlow nodes
  const rfNodes: Node[] = useMemo(() => {
    const isModuleOrMacro = selectedItem?.type === "module" || selectedItem?.type === "macro";
    
    if (isModuleOrMacro) {
      // Show ONLY the DD Node, positioned at a nice centered y-coordinate (e.g. y = 190)
      return [
        {
          id: "dd_excel",
          type: "l3ExcelNode",
          position: { x: 80, y: 190 },
          data: {
            nodeKey: "dd_excel",
            label: selectedItem?.type === "module" ? "DD Module Excel" : "DD Macro Excel",
            icon: "📄",
            color: "#06b6d4",
            description: "Detail Design — プログラム仕様書",
            status: ddStatus.status,
            outputFile: ddStatus.outputFile,
            outputSizeKb: ddStatus.outputSizeKb,
            errorMsg: ddStatus.errorMsg,
            duration: ddStatus.duration,
            selectedInput: selectedName,
            hasData: selectedItem?.has_dd ?? false,
            onGenerate: handleGenDd,
            onDownload: () => ddStatus.downloadUrl && ddStatus.outputFile
              ? handleDownload(ddStatus.downloadUrl, ddStatus.outputFile) : undefined,
          },
        }
      ];
    } else {
      // Show BOTH BD and DD Nodes (for form and report types)
      return [
        {
          id: "bd_excel",
          type: "l3ExcelNode",
          position: BD_NODE_POS,
          data: {
            nodeKey: "bd_excel",
            label: selectedItem?.type === "report" ? "BD Report Excel" : "BD Screen Excel",
            icon: "📊",
            color: "#f59e0b",
            description: "Basic Design — 画面仕様書",
            status: bdStatus.status,
            outputFile: bdStatus.outputFile,
            outputSizeKb: bdStatus.outputSizeKb,
            errorMsg: bdStatus.errorMsg,
            duration: bdStatus.duration,
            selectedInput: selectedName,
            hasData: selectedItem?.has_bd ?? false,
            onGenerate: handleGenBd,
            onDownload: () => bdStatus.downloadUrl && bdStatus.outputFile
              ? handleDownload(bdStatus.downloadUrl, bdStatus.outputFile) : undefined,
          },
        },
        {
          id: "dd_excel",
          type: "l3ExcelNode",
          position: DD_NODE_POS,
          data: {
            nodeKey: "dd_excel",
            label: selectedItem?.type === "report" ? "DD Report Excel" : "DD Form Excel",
            icon: "📄",
            color: "#06b6d4",
            description: "Detail Design — プログラム仕様書",
            status: ddStatus.status,
            outputFile: ddStatus.outputFile,
            outputSizeKb: ddStatus.outputSizeKb,
            errorMsg: ddStatus.errorMsg,
            duration: ddStatus.duration,
            selectedInput: selectedName,
            hasData: selectedItem?.has_dd ?? false,
            onGenerate: handleGenDd,
            onDownload: () => ddStatus.downloadUrl && ddStatus.outputFile
              ? handleDownload(ddStatus.downloadUrl, ddStatus.outputFile) : undefined,
          },
        },
      ];
    }
  }, [selectedName, selectedItem, bdStatus, ddStatus, handleGenBd, handleGenDd, handleDownload]);

  const rfEdges: Edge[] = useMemo(() => {
    const isModuleOrMacro = selectedItem?.type === "module" || selectedItem?.type === "macro";
    if (isModuleOrMacro) {
      return [];
    }
    return [{
      id: "bd-dd",
      source: "bd_excel", sourceHandle: "bottom",
      target: "dd_excel", targetHandle: "top",
      animated: bdStatus.status === "success",
      style: { stroke: bdStatus.status === "success" ? "var(--warning)" : "var(--border-color)", strokeWidth: 2 },
    }];
  }, [bdStatus.status, selectedItem]);

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges);

  useEffect(() => {
    setNodes(prev => {
      if (!prev || prev.length === 0) return rfNodes;
      return prev.map(pn => {
        const match = rfNodes.find(n => n.id === pn.id);
        return match ? { ...pn, data: match.data } : pn;
      });
    });
  }, [rfNodes, setNodes]);

  useEffect(() => { setEdges(rfEdges); }, [rfEdges, setEdges]);

  const getLogColor = (level: string) =>
    level === "ERROR" ? "var(--danger)" : level === "SUCCESS" ? "var(--success)" : level === "WARN" ? "var(--warning)" : "var(--info)";

  const toggleGroup = (g: string) => setCollapsedGroups(prev => ({ ...prev, [g]: !prev[g as keyof typeof prev] }));

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <Header />

      <main className="layout-content">
        {/* ── Left Sidebar ── */}
        <div className="task-sidebar" style={{ width: sidebarCollapsed ? 40 : 240, flexShrink: 0, transition: "width 0.22s", overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", padding: sidebarCollapsed ? "12px 8px" : "10px 12px", borderBottom: "1px solid var(--border-color)", gap: 6, minHeight: 42 }}>
            {!sidebarCollapsed && <span style={{ color: "var(--text-muted)", fontSize: 12, fontWeight: 600, flex: 1 }}><strong style={{ color: "var(--text-main)" }}>L3</strong> Items</span>}
            <button onClick={() => setSidebarCollapsed(v => !v)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex", padding: 2, borderRadius: 4 }}>
              {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: "rotate(180deg)" }} />}
            </button>
          </div>
          {!sidebarCollapsed && (
            <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column" }}>
              <div style={{ padding: "12px 12px 6px 12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                <button
                  onClick={handleGenAll}
                  disabled={!selectedName}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                    width: "100%",
                    padding: "8px 14px", borderRadius: 6, border: "none",
                    background: selectedName
                      ? "var(--brand-gradient)"
                      : "var(--border-color)",
                    color: selectedName ? "#fff" : "var(--text-muted)",
                    fontSize: 12, fontWeight: 700, cursor: selectedName ? "pointer" : "not-allowed",
                    boxShadow: selectedName ? "0 4px 12px var(--brand-glow)" : "none",
                    transition: "all 0.2s"
                  }}
                >
                  {selectedItem?.type === "module" || selectedItem?.type === "macro" ? "⚡ Gen DD" : "⚡ Gen All"}
                </button>

                <div className="task-search-container" style={{ padding: "12px 0 0 0", borderBottom: "none" }}>
                  <div style={{ position: "relative" }}>
                    <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                    <input type="text" placeholder="Tìm theo tên…" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                      className="task-search-input" />
                  </div>
                </div>
                <div style={{ marginTop: 6, fontSize: 9, color: "var(--text-muted)", display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span>🟢 BD+DD</span><span>🟡 BD only</span><span>🔵 DD only</span><span>⚪ none</span>
                </div>
              </div>
              {(["forms", "reports", "modules", "macros"] as const).map(group => {
                const typeMap: Record<string, string> = { forms: "form", reports: "report", modules: "module", macros: "macro" };
                const countMap: Record<string, number> = { forms: groupCounts.forms, reports: groupCounts.reports, modules: groupCounts.modules, macros: groupCounts.macros };
                const labelMap: Record<string, string> = { forms: "🖥️ Forms", reports: "📊 Reports", modules: "📦 Modules", macros: "⚙️ Macros" };
                const groupItems = filteredItems.filter(i => i.type === typeMap[group]);
                return (
                  <div key={group}>
                    <div className="task-group-title" onClick={() => toggleGroup(group)}>
                      {collapsedGroups[group] ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                      {labelMap[group]}
                      <span style={{ marginLeft: "auto", fontSize: 10, background: "var(--border-color)", color: "var(--text-main)", borderRadius: 10, padding: "1px 6px", fontWeight: 700 }}>{countMap[group]}</span>
                    </div>
                    {!collapsedGroups[group] && groupItems.map((item, idx) => (
                      <div key={`${group}-${idx}`}
                        onClick={() => setSelectedName(item.name)}
                        className={`task-item ${selectedName === item.name ? "active" : ""}`}
                        style={{
                          padding: "6px 16px 6px 24px",
                          borderLeftWidth: 3
                        }}>
                        <span style={{ fontSize: 10, flexShrink: 0 }} title={
                          item.has_bd && item.has_dd ? "BD + DD available"
                          : item.has_bd ? "BD only (no DD yet)"
                          : item.has_dd ? "DD only (no BD yet)"
                          : "Not generated yet"
                        }>
                          {item.has_bd && item.has_dd ? "🟢" : item.has_bd ? "🟡" : item.has_dd ? "🔵" : "⚪"}
                        </span>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }} title={item.name}>{item.name}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Center: ReactFlow ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes} minZoom={0.3} maxZoom={1.5} proOptions={{ hideAttribution: true }}
              onInit={rf => setTimeout(() => rf.fitView({ padding: 0.4 }), 50)}>
              <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--border-color)" />
              <Controls style={{ background: "var(--bg-panel)", fill: "var(--text-main)" }} />
            </ReactFlow>
          </div>
        </div>

        {/* ── Right Sidebar: Logs + Files ── */}
        <div className="terminal-sidebar" style={{ width: 360 }}>
          <div style={{ display: "flex", borderBottom: "1px solid var(--border-color)", backgroundColor: "var(--bg-tab-bar)" }}>
            <div onClick={() => setRightTab("logs")} style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "logs" ? "var(--success)" : "var(--text-muted)", borderBottom: rightTab === "logs" ? "2px solid var(--success)" : "2px solid transparent" }}>
              <Settings2 size={13} /> Logs
            </div>
            <div onClick={() => { setRightTab("files"); refreshOutputs(); }} style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: rightTab === "files" ? "var(--warning)" : "var(--text-muted)", borderBottom: rightTab === "files" ? "2px solid var(--warning)" : "2px solid transparent" }}>
              <Eye size={13} /> Files ({outputFiles.length})
            </div>
          </div>

          {rightTab === "logs" && (
            <div className="terminal-content" style={{ overflowY: "auto", flex: 1, padding: 16 }}>
              {logs.map((log, i) => (
                <div key={i} className="log-line">
                  <span className="log-time">[{log.time}]</span>
                  <span style={{ color: getLogColor(log.level), fontWeight: "bold" }}> [{log.level}]</span>
                  <span style={{ marginLeft: 6, color: "var(--text-main)" }}>{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}

          {rightTab === "files" && (
            <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
              {outputFiles.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", marginTop: 32 }}>
                  <FileSpreadsheet size={28} style={{ margin: "0 auto 8px", display: "block", opacity: 0.4 }} /><br />
                  No Excel files generated yet.<br />Select an item and click Generate.
                </div>
              ) : outputFiles.map((f, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 8px", borderBottom: "1px solid var(--border-color)", borderRadius: 4 }}>
                  <span style={{ fontSize: 16 }}>{f.doc_kind === "BD" ? "📊" : "📄"}</span>
                  <div style={{ flex: 1, overflow: "hidden" }}>
                    <div style={{ fontSize: 11, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={f.filename}>{f.filename}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{f.doc_kind} {f.doc_type} — {f.size_kb} KB</div>
                  </div>
                  <button onClick={() => handleDownload(f.download_url, f.filename)}
                    style={{ background: "none", border: "1px solid var(--border-color)", color: "var(--accent)", borderRadius: 4, padding: "3px 6px", cursor: "pointer", display: "flex", alignItems: "center" }}>
                    <Download size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
