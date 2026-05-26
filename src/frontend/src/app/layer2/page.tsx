"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import Link from "next/link";
import { Settings2, Terminal, DatabaseZap, Search, ChevronDown, ChevronRight, BarChart2, Download, Bot, FileSpreadsheet, Database, Cpu, Sparkles } from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
// @ts-ignore
import { ReactFlow, Controls, Background, Node, Edge, useNodesState, useEdgesState, BackgroundVariant } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Import Custom Nodes
import { DbQueryNode } from "../../components/nodes/DbQueryNode";
import { AgentNode } from "../../components/nodes/AgentNode";
import { DdAgentNode } from "../../components/nodes/DdAgentNode";
import { OutputNode } from "../../components/nodes/OutputNode";
import { GraphView } from "../../components/GraphView";


interface LogEntry {
  time: string;
  level: string;
  message: string;
}

export default function Layer2Workflow() {
  const [dbScreens, setDbScreens] = useState<{key: string, name: string, type?: string}[]>([]);
  const [models, setModels] = useState<string[]>(["deepseek-v4-pro", "deepseek-v4-flash", "qwen3-vl-235b-a22b-thinking", "qwen-vl-plus-latest", "qwen-max", "qvq-max-2025-03-25"]);

  const [viewMode, setViewMode] = useState<"screen" | "module" | "macro">("screen");

  // Sidebar State
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
    forms: false,
    reports: false,
    modules: false,
    macros: false
  });

  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => ({ ...prev, [group]: !prev[group] }));
  };

  const filteredSidebarScreens = useMemo(() => {
    if (!searchQuery.trim()) return dbScreens;
    const lowerQ = searchQuery.toLowerCase();
    return dbScreens.filter(s => s.name.toLowerCase().includes(lowerQ));
  }, [dbScreens, searchQuery]);

  // Left sidebar collapse
  const [taskSidebarCollapsed, setTaskSidebarCollapsed] = useState(false);

  // Logs state
  const [systemLogs, setSystemLogs] = useState<LogEntry[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);
  
  // Right Sidebar State
  const [activeTab, setActiveTab] = useState<"logs" | "preview" | "tokens">("logs");
  const [centerView, setCenterView] = useState<"node" | "graph" | "graphWpf">("node");
  const [sidebarWidth, setSidebarWidth] = useState(480);
  const isResizing = useRef(false);

  const addLog = (level: string, message: string) => {
    const time = new Date().toLocaleTimeString('vi-VN', { hour12: false });
    setSystemLogs(prev => [...prev, { time, level, message }]);
  };

  // Workflow State
  const [screenName, setScreenName] = useState("");
  const [queryStatus, setQueryStatus] = useState<"idle"|"running"|"success"|"error">("idle");
  const [dbData, setDbData] = useState<any>(null);

  const [selectedModel, setSelectedModel] = useState(models[0]);
  const [agentStatus, setAgentStatus] = useState<"idle"|"running"|"success"|"error">("idle");
  const [agentStep, setAgentStep] = useState<"s1"|"s2"|"s3"|"s4"|"done">("s1");
  const [resultJson, setResultJson] = useState("");

  // DD Agent state
  const [ddSelectedModel, setDdSelectedModel] = useState(models[0]);
  const [ddAgentStatus, setDdAgentStatus] = useState<"idle"|"running"|"success"|"error">("idle");
  const [ddAgentStep, setDdAgentStep] = useState<"d1"|"d2"|"d3"|"d4"|"done">("d1");
  const [ddResultJson, setDdResultJson] = useState("");

  // Token Stats state
  interface TokenRecord { item: string; model: string; stage: string; input_tokens: number; output_tokens: number; cost_usd: number; }
  interface TokenStats { total_tokens: number; total_cost_usd: number; records: TokenRecord[]; }
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);
  const [ddTokenStats, setDdTokenStats] = useState<TokenStats | null>(null);
  const [lastLogFile, setLastLogFile] = useState<string>("");

  // Model health status: { [modelId]: { status: 'ok'|'error'|'quota_exceeded'|'testing' } }
  const [modelHealth, setModelHealth] = useState<Record<string, {status: string; error?: string}>>({});

  const [previewMode, setPreviewMode] = useState<"json" | "jsonl" | "xml">("json");
  const [copyStatus, setCopyStatus] = useState<"json" | "jsonl" | "xml" | null>(null);

  const fullJsonString = useMemo(() => {
    if (!dbData) return "";
    if (previewMode === "xml") {
      if (dbData.macro && dbData.macro.raw_xml) {
        return dbData.macro.raw_xml;
      }
      return "Không có mã nguồn XML cho đối tượng này.";
    }
    if (previewMode === "jsonl") {
      if (dbData.form && Array.isArray(dbData.form.controls)) {
        return dbData.form.controls.map((c: any) => JSON.stringify(c)).join("\n");
      } else if (dbData.report && Array.isArray(dbData.report.sections)) {
        return dbData.report.sections.map((c: any) => JSON.stringify(c)).join("\n");
      } else {
        return JSON.stringify(dbData) + "\n";
      }
    }
    return JSON.stringify(dbData, null, 2);
  }, [dbData, previewMode]);

  const nodeTypes = useMemo(() => ({
    dbNode: DbQueryNode,
    agentNode: AgentNode,
    ddAgentNode: DdAgentNode,
    outputNode: OutputNode,
  }), []);


  // Filter items based on active tab
  const filteredScreens = useMemo(() => {
    if (viewMode === "screen") {
      return dbScreens.filter(s => !s.type || ["form", "report"].includes(s.type));
    } else if (viewMode === "module") {
      return dbScreens.filter(s => s.type === "module");
    } else {
      return dbScreens.filter(s => s.type === "macro");
    }
  }, [dbScreens, viewMode]);

  // Sync ReactFlow internal data with top-level state
  const commonData = {
    screenName, setScreenName,
    queryStatus, handleQueryDB: () => handleQueryDB(),
    dbData, setActiveTab,
    selectedModel, setSelectedModel,
    agentStatus, agentStep, handleRunAgent: () => handleRunAgent(),
    ddSelectedModel, setDdSelectedModel,
    ddAgentStatus, ddAgentStep, handleRunDdAgent: () => handleRunDdAgent(),
    models, mockScreens: filteredScreens, resultJson, ddResultJson,
    viewMode, modelHealth
  };



  const initialNodesScreen: Node[] = [
    { id: '2', type: 'dbNode',      position: { x: 50,  y: 180 }, data: commonData },
    { id: '3', type: 'agentNode',   position: { x: 400, y: 180 }, data: commonData },
    { id: '4', type: 'ddAgentNode', position: { x: 750, y: 180 }, data: commonData },
    { id: '5', type: 'outputNode',  position: { x: 1100, y: 80  }, data: commonData },
  ];

  const initialEdgesScreen: Edge[] = [
    { id: 'e2-3', source: '2', target: '3', animated: agentStatus === 'running' || agentStatus === 'success',  style: { stroke: queryStatus === 'success' ? '#3b82f6' : "var(--border-color)", strokeWidth: 2 } },
    { id: 'e3-4', source: '3', target: '4', animated: ddAgentStatus === 'running' || ddAgentStatus === 'success', style: { stroke: agentStatus === 'success' ? '#f97316' : "var(--border-color)", strokeWidth: 2 } },
    { id: 'e4-5', source: '4', target: '5', animated: ddAgentStatus === 'success', style: { stroke: ddAgentStatus === 'success' ? '#8b5cf6' : "var(--border-color)", strokeWidth: 2 } },
  ];

  const initialNodesModule: Node[] = [
    { id: '2', type: 'dbNode',      position: { x: 50,  y: 180 }, data: commonData },
    { id: '4', type: 'ddAgentNode', position: { x: 400, y: 180 }, data: commonData },
    { id: '5', type: 'outputNode',  position: { x: 750, y: 180 }, data: commonData },
  ];

  const initialEdgesModule: Edge[] = [
    { id: 'e2-4', source: '2', target: '4', animated: ddAgentStatus === 'running' || ddAgentStatus === 'success', style: { stroke: queryStatus === 'success' ? '#f97316' : "var(--border-color)", strokeWidth: 2 } },
    { id: 'e4-5', source: '4', target: '5', animated: ddAgentStatus === 'success', style: { stroke: ddAgentStatus === 'success' ? '#8b5cf6' : "var(--border-color)", strokeWidth: 2 } },
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodesScreen);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdgesScreen);

  useEffect(() => {
    const nds = viewMode === "screen" ? initialNodesScreen : initialNodesModule;
    const eds = viewMode === "screen" ? initialEdgesScreen : initialEdgesModule;
    
    setNodes(nds.map(node => ({ ...node, data: { ...node.data, ...commonData } })));
    setEdges(eds);
  }, [viewMode, screenName, queryStatus, dbData, selectedModel, agentStatus, resultJson, agentStep, ddSelectedModel, ddAgentStatus, ddAgentStep, ddResultJson, models]);





  useEffect(() => {
    // Reset trạng thái pipeline khi đổi screen
    setQueryStatus("idle"); setDbData(null); setResultJson("");
    setDdAgentStatus("idle"); setDdAgentStep("d1"); setDdResultJson("");
    setActiveTab("logs");

    // Luôn reset BD agent trước, rồi check xem file s4 có tồn tại không
    setAgentStatus("idle"); setAgentStep("s1");

    if (!screenName) return;

    // Abort controller để tránh race condition khi đổi screen nhanh
    const controller = new AbortController();

    fetch(`/api/v1/layer2/bd-status/${encodeURIComponent(screenName)}`, { signal: controller.signal })
      .then(r => r.json())
      .then(data => {
        if (!data.success) return;
        if (data.bd_done) {
          setAgentStatus("success");
          setAgentStep("done");
          addLog("INFO", `[BD Cache] s4_bd_final đã có cho '${screenName}' — BD agent đã hoàn thành.`);
        }
        if (data.dd_done) {
          setDdAgentStatus("success");
          setDdAgentStep("done");
          addLog("INFO", `[DD Cache] d4_dd_final đã có cho '${screenName}' — DD agent đã hoàn thành.`);
        }
      })
      .catch(err => {
        if (err.name !== "AbortError") {
          // ignore network errors — giữ trạng thái idle
        }
      });

    return () => controller.abort();
  }, [screenName]);


  useEffect(() => {
    addLog("INFO", "Initializing Node-based System Components...");
    setTimeout(() => addLog("INFO", "Connecting to Python Layer1 Repo..."), 400);

    // Fetch model list từ config.json qua /api/v1/layer2/config
    fetch("/api/v1/layer2/config")
    .then(res => res.json())
    .then(data => {
      if (data.models && Array.isArray(data.models)) {
        const modelIds = data.models.map((m: {id: string}) => m.id);
        setModels(modelIds);
        setSelectedModel(modelIds[0] || "deepseek-v4-flash");
        setDdSelectedModel(modelIds[0] || "deepseek-v4-flash");
        // Mark all as 'testing' then fetch health
        const initHealth: Record<string, {status: string}> = {};
        modelIds.forEach((id: string) => { initHealth[id] = { status: 'testing' }; });
        setModelHealth(initHealth);
        fetch("/api/v1/layer2/models/health")
          .then(r => r.json())
          .then(hd => { if (hd.success) setModelHealth(hd.results); })
          .catch(() => {});
      }

    })
    .catch(() => { /* fallback to defaults already set */ });

    // Fetch dynamic screen list through dedicated API (Unified list)
    fetch("/api/items")
    .then(res => res.json())
    .then(data => {
      if (data.success && Array.isArray(data.result)) {
        setDbScreens(data.result);
        
        // Initial filter for screen mode
        const screenItems = data.result.filter((s: any) => !s.type || ["form", "report"].includes(s.type));
        if (screenItems.length > 0) {
          setScreenName(screenItems[0].name);
          setViewMode("screen");
        }
        
        addLog("SUCCESS", `Loaded ${data.result.length} items from Database.`);
      } else {
        const errorMsg = data.error || "DB is empty or invalid data format.";
        addLog("WARN", `Failed to load items: ${errorMsg}`);
      }
    })
    .catch(err => {
      addLog("ERROR", `Failed to connect DB for item list: ${err.message}`);
    });

    setTimeout(() => addLog("SUCCESS", "React Flow Canvas Ready!"), 1000);
  }, []);

  useEffect(() => {
    if (activeTab === "logs") {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [systemLogs, activeTab]);

  // Handle Resize Sidebar
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = document.body.clientWidth - e.clientX;
      if (newWidth > 300 && newWidth < document.body.clientWidth * 0.8) {
        setSidebarWidth(newWidth);
      }
    };
    const handleMouseUp = () => { isResizing.current = false; };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  async function handleQueryDB() {
    if (!screenName) return;
    setQueryStatus("running"); setAgentStatus("idle"); setResultJson(""); setDbData(null); setActiveTab("logs");
    addLog("INFO", `--- DATA FETCH ---`);
    addLog("INFO", `Calling \`layer1_repo.py\` to resolve dependencies for screen: ${screenName}`);
    
    try {
      const res = await fetch("/api/db-query", {
        method: "POST", 
        headers: { "Content-Type": "application/json" }, 
        body: JSON.stringify({ 
          screenName, 
          itemType: "auto",
          deep: viewMode === "module" || viewMode === "macro" 
        })
      });
      const data = await res.json();
      if (data.success) {
        setQueryStatus("success");
        addLog("SUCCESS", `layer1_repo.py returned exact logical context (bd_code_json).`);
        setDbData(data.result);
        const byteSize = (JSON.stringify(data.result).length / 1024).toFixed(2);
        addLog("INFO", `Loaded: ${byteSize} KB of parsed python AST context.`);
      } else {
        setQueryStatus("error"); setDbData(null); addLog("ERROR", `Lỗi từ Backend: ${data.error}`);
      }
    } catch (error: any) {
      setQueryStatus("error"); setDbData(null); addLog("ERROR", `Network Exception: ${error.message}`);
    }
  }

  async function handleRunAgent() {
    if (!screenName || queryStatus !== "success" || !dbData) return;
    setAgentStatus("running"); setAgentStep("s1"); setResultJson(""); setActiveTab("logs");
    addLog("INFO", `--- LLM EXECUTION ---`);
    addLog("INFO", `Model Triggered: ${selectedModel}`);
    
    // Simulate progression for better UX since API is synchronous
    const s2Timer = setTimeout(() => setAgentStep("s2"), 1500); // s1 usually fast
    const s3Timer = setTimeout(() => setAgentStep("s3"), 3500); // s2 takes a bit
    
    try {
      const res = await fetch("/api/v1/layer2/bd-flow-full", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ screenName, model: selectedModel, dbData })
      });
      
      clearTimeout(s2Timer);
      clearTimeout(s3Timer);
      
      // Flash S4 quickly for UX before marking done
      setAgentStep("s4");
      setTimeout(() => setAgentStep("done"), 500);
      
      const data = await res.json();
      if (data.success) {
        setAgentStatus("success"); setResultJson(data.result);
        addLog("SUCCESS", `Full BD Flow (s1->s2->s3->s4) executed successfully.`);
        if (data.paths) {
          addLog("INFO", `[s1_form] Saved: ${data.paths.s1_source_file}`);
          addLog("INFO", `[s2_mapping] Saved: ${data.paths.s2_mapping_file}`);
          addLog("INFO", `[s3_logic] Extracted ${data.paths.logic_items_processed} items to: ${data.paths.s3_logic_jsonl}`);
          addLog("INFO", `[s3_logic] Event results saved: ${data.paths.s3_logic_result}`);
          addLog("INFO", `[s3_logic] Screen summary saved: ${data.paths.s3_logic_summary}`);
          addLog("SUCCESS", `[s4_final] Merged mapping & logic into: ${data.paths.s4_final_file}`);
        }
        if (data.token_stats) {
          const ts = data.token_stats;
          setTokenStats(ts);
          addLog("INFO", `━━━━━━ TOKEN USAGE (${ts.flow_type || "BD"}) ━━━━━━`);
          addLog("INFO", `📊 Tổng: ${ts.total_tokens.toLocaleString()} tokens  |  💰 Chi phí: $${ts.total_cost_usd.toFixed(5)}`);
          if (ts.records?.length > 0) {
            ts.records.forEach((r: any) => {
              addLog("INFO", `  • [${r.stage}] ${r.item} — in:${r.input_tokens} out:${r.output_tokens} → $${r.cost_usd.toFixed(5)}`);
            });
          }
          if (data.log_files?.excel) setLastLogFile(data.log_files.excel);
          setActiveTab("tokens");
        }
      } else {
        setAgentStatus("error"); setResultJson(`Lỗi: ${data.error}`); addLog("ERROR", `API Call Failed: ${data.error}`);
      }
    } catch (error: any) {
      clearTimeout(s2Timer);
      clearTimeout(s3Timer);
      setAgentStatus("error"); setResultJson(`Lỗi mạng: ${error.message}`); addLog("ERROR", `Network Exception: ${error.message}`);
    }
  }

  async function handleRunDdAgent() {
    const isModuleMode = viewMode === "module" || viewMode === "macro";
    // For screens, we need BD agent success. For modules/macros, we only need DB Query success.
    if (!screenName) return;
    if (!isModuleMode && agentStatus !== "success") return;
    if (isModuleMode && queryStatus !== "success") return;
    
    setDdAgentStatus("running"); setDdAgentStep("d1"); setDdResultJson(""); setActiveTab("logs");
    addLog("INFO", `--- DD EXECUTION ---`);
    addLog("INFO", `[D1] Fetching DD Source from DB ...`);


    // Simulate step progression for UX
    const d2Timer = setTimeout(() => { setDdAgentStep("d2"); addLog("INFO", `[D2] Mapping SQL/Table to query sheets ...`); }, 1500);
    const d3Timer = setTimeout(() => { setDdAgentStep("d3"); addLog("INFO", `[D3] LLM generating detail steps per module ...`); }, 3000);

    try {
      const res = await fetch("/api/dd-flow-full", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ screenName, model: ddSelectedModel }),
      });


      clearTimeout(d2Timer);
      clearTimeout(d3Timer);

      setDdAgentStep("d4");
      setTimeout(() => setDdAgentStep("done"), 400);

      const data = await res.json();
      if (data.success) {
        setDdAgentStatus("success"); setDdResultJson(data.result);
        addLog("SUCCESS", `Full DD Flow (D1→D4) executed successfully.`);
        if (data.paths) {
          addLog("INFO",    `[D1] Source saved: ${data.paths.d1_source_file}`);
          addLog("INFO",    `[D2] Mapping saved: ${data.paths.d2_mapping_file}`);
          addLog("INFO",    `[D3] Logic saved: ${data.paths.d3_output_json || data.paths.d3_logic_jsonl} (${data.paths.d3_modules_processed}/${data.paths.logic_items_total} modules)`);
          addLog("SUCCESS", `[D4] Final DD saved: ${data.paths.d4_final_file}`);
        }
        if (data.token_stats) {
          const ts = data.token_stats;
          setDdTokenStats(ts);
          addLog("INFO", `━━━━━━ TOKEN USAGE (${ts.flow_type || "DD"}) ━━━━━━`);
          addLog("INFO", `📊 Tổng: ${ts.total_tokens.toLocaleString()} tokens  |  💰 Chi phí: $${ts.total_cost_usd.toFixed(5)}`);
          if (ts.records?.length > 0) {
            ts.records.forEach((r: any) => {
              addLog("INFO", `  • [${r.stage}] ${r.item} — in:${r.input_tokens} out:${r.output_tokens} → $${r.cost_usd.toFixed(5)}`);
            });
          } else if (ts.note) {
            addLog("WARN", `💡 ${ts.note}`);
          }
          if (data.log_files?.excel) setLastLogFile(data.log_files.excel);
          setActiveTab("tokens");
        }
      } else {
        setDdAgentStatus("error"); setDdResultJson(`Lỗi: ${data.error}`);
        addLog("ERROR", `DD Flow Failed: ${data.error}`);
      }
    } catch (error: any) {
      clearTimeout(d2Timer);
      clearTimeout(d3Timer);
      setDdAgentStatus("error"); setDdResultJson(`Lỗi mạng: ${error.message}`);
      addLog("ERROR", `DD Network Exception: ${error.message}`);
    }
  }

  const copyToClipboardFallback = async (text: string, successMsg: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        addLog("SUCCESS", successMsg);
      } else {
        // Dự phòng cho trường hợp LAN IP HTTP (không có SecureContext hỗ trợ Navigator API)
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "absolute";
        textArea.style.left = "-999999px";
        document.body.prepend(textArea);
        textArea.select();
        try {
          document.execCommand('copy');
          addLog("SUCCESS", successMsg + " (Fallback Mode)");
          return true;
        } catch (error) {
          addLog("ERROR", "Lỗi trình duyệt không cho phép Copy.");
          return false;
        } finally {
          textArea.remove();
        }
      }
    } catch (err: any) {
      addLog("ERROR", `Clipboard Error: ${err.message}`);
      return false;
    }
  };

  const handleCopyJson = async () => {
    setPreviewMode("json");
    const text = JSON.stringify(dbData, null, 2);
    await copyToClipboardFallback(text, "Đã copy toàn bộ JSON vào Clipboard!");
    setCopyStatus("json");
    setTimeout(() => setCopyStatus(null), 2000);
  };

  const handleCopyJsonL = async () => {
    setPreviewMode("jsonl");
    let jsonl = "";
    if (dbData && dbData.form && Array.isArray(dbData.form.controls)) {
      jsonl = dbData.form.controls.map((c: any) => JSON.stringify(c)).join("\n");
      await copyToClipboardFallback(jsonl, "Phát hiện Array Controls: Chuyển cấu trúc & Copy JSONL thành công!");
    } else if (dbData && dbData.report && Array.isArray(dbData.report.sections)) {
      jsonl = dbData.report.sections.map((c: any) => JSON.stringify(c)).join("\n");
      await copyToClipboardFallback(jsonl, "Phát hiện Report Sections: Chuyển cấu trúc & Copy JSONL thành công!");
    } else {
      jsonl = JSON.stringify(dbData) + "\n";
      await copyToClipboardFallback(jsonl, "Đã copy dữ liệu sang dạng JSONL (1 dòng) vào Clipboard!");
    }
    setCopyStatus("jsonl");
    setTimeout(() => setCopyStatus(null), 2000);
  };

  const getLogColor = (level: string) => {
    if (level === 'ERROR') return '#ef4444';
    if (level === 'SUCCESS') return '#10b981';
    if (level === 'WARN') return '#f59e0b';
    return '#60a5fa'; // INFO
  };

  return (
    <>
      <Header />
      
      <main className="layout-content">
        {/* Left Task Sidebar */}
        <div className="task-sidebar" style={{
          width: taskSidebarCollapsed ? 40 : 250,
          flexShrink: 0,
          transition: 'width 0.22s cubic-bezier(.4,0,.2,1)',
          overflow: 'hidden',
          position: 'relative',
        }}>
          {/* Header row with toggle */}
          <div style={{ display: 'flex', alignItems: 'center', padding: taskSidebarCollapsed ? '12px 8px' : '10px 12px', borderBottom: '1px solid var(--border-color)', gap: 6, flexShrink: 0, minHeight: 42 }}>
            {!taskSidebarCollapsed && (
              <span style={{ color: "var(--text-muted)", fontSize: '12px', fontWeight: 600, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden' }}>
                <strong style={{ color: "var(--text-main)" }}>vba_brain</strong> Explorer
              </span>
            )}
            <button
              onClick={() => setTaskSidebarCollapsed(v => !v)}
              title={taskSidebarCollapsed ? 'Mở Task Explorer' : 'Thu gọn Task Explorer'}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: "var(--text-muted)", display: 'flex', alignItems: 'center', padding: 2, borderRadius: 4, flexShrink: 0 }}
            >
              {taskSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
            </button>
          </div>

          {/* Collapsed icon strip */}
          {taskSidebarCollapsed && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '6px 0', gap: 2 }}>
              {dbScreens.filter(s => !s.type || ['form','report'].includes(s.type)).slice(0, 8).map((item, idx) => (
                <div key={idx} title={item.name}
                  onClick={() => { setScreenName(item.name); setViewMode('screen'); setCenterView('graph'); setTaskSidebarCollapsed(false); }}
                  style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6, cursor: 'pointer', background: screenName === item.name ? 'rgba(59,130,246,0.2)' : 'transparent' }}>
                  <DatabaseZap size={13} style={{ color: screenName === item.name ? '#3b82f6' : "var(--text-muted)" }} />
                </div>
              ))}
            </div>
          )}

          {/* Full sidebar content */}
          {!taskSidebarCollapsed && (
            <div style={{ overflowY: 'auto', flex: 1 }}>
              <div className="task-search-container">
                <div style={{ position: 'relative' }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input 
                    type="text" 
                    className="task-search-input" 
                    placeholder="Tìm theo tên..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>

              <div className="task-group-title" onClick={() => toggleGroup('forms')}>
                {collapsedGroups.forms ? <ChevronRight size={14} /> : <ChevronDown size={14} />} Forms
              </div>
              {!collapsedGroups.forms && filteredSidebarScreens.filter(s => (s.type === "form" && !s.name.toUpperCase().startsWith("R")) || (!s.type && s.name.toUpperCase().startsWith("F"))).map((item, idx) => (
                <div key={`form-${idx}`} 
                     className={`task-item ${screenName === item.name ? 'active' : ''}`}
                     onClick={() => { setScreenName(item.name); setViewMode("screen"); setCenterView("graph"); }}>
                  <DatabaseZap size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              <div className="task-group-title" style={{ marginTop: '8px' }} onClick={() => toggleGroup('reports')}>
                {collapsedGroups.reports ? <ChevronRight size={14} /> : <ChevronDown size={14} />} Reports
              </div>
              {!collapsedGroups.reports && filteredSidebarScreens.filter(s => s.type === "report" || (["form", "report", undefined].includes(s.type) && s.name.toUpperCase().startsWith("R"))).map((item, idx) => (
                <div key={`report-${idx}`} 
                     className={`task-item ${screenName === item.name ? 'active' : ''}`}
                     onClick={() => { setScreenName(item.name); setViewMode("screen"); setCenterView("graph"); }}>
                  <DatabaseZap size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              <div className="task-group-title" style={{ marginTop: '8px' }} onClick={() => toggleGroup('modules')}>
                {collapsedGroups.modules ? <ChevronRight size={14} /> : <ChevronDown size={14} />} Modules
              </div>
              {!collapsedGroups.modules && filteredSidebarScreens.filter(s => s.type === "module").map((item, idx) => (
                <div key={`mod-${idx}`} 
                     className={`task-item ${screenName === item.name ? 'active' : ''}`}
                     onClick={() => { setScreenName(item.name); setViewMode("module"); setCenterView("graph"); }}>
                  <Terminal size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}

              <div className="task-group-title" style={{ marginTop: '8px' }} onClick={() => toggleGroup('macros')}>
                {collapsedGroups.macros ? <ChevronRight size={14} /> : <ChevronDown size={14} />} Macros
              </div>
              {!collapsedGroups.macros && filteredSidebarScreens.filter(s => s.type === "macro").map((item, idx) => (
                <div key={`mac-${idx}`} 
                     className={`task-item ${screenName === item.name ? 'active' : ''}`}
                     onClick={() => { setScreenName(item.name); setViewMode("macro"); setCenterView("graph"); }}>
                  <Settings2 size={14} className="task-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.name}>{item.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
          {/* Center Top View Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', background: '#151822', borderBottom: '1px solid var(--border-color)', flexShrink: 0 }}>
            <button
              onClick={() => setCenterView('node')}
              style={{ padding: '5px 14px', fontSize: '12px', fontWeight: 600, borderRadius: 6, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', background: centerView === 'node' ? '#3b82f6' : 'rgba(59,130,246,0.1)', color: centerView === 'node' ? '#fff' : '#60a5fa', transition: 'all 0.2s' }}
            >
              ⬡ Task Node
            </button>
            <button
              onClick={() => setCenterView('graph')}
              style={{ padding: '5px 14px', fontSize: '12px', fontWeight: 600, borderRadius: 6, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', background: centerView === 'graph' ? '#a855f7' : 'rgba(168,85,247,0.1)', color: centerView === 'graph' ? '#fff' : '#c084fc', transition: 'all 0.2s' }}
            >
              🕸 Graph View (VBA)
            </button>
            <button
              onClick={() => setCenterView('graphWpf')}
              style={{ padding: '5px 14px', fontSize: '12px', fontWeight: 600, borderRadius: 6, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', background: centerView === 'graphWpf' ? '#0891b2' : 'rgba(8,145,178,0.12)', color: centerView === 'graphWpf' ? '#fff' : '#22d3ee', transition: 'all 0.2s' }}
            >
              ◈ WPF Graph
            </button>
            {screenName && (
              <span style={{ marginLeft: 8, fontSize: '12px', color: "var(--text-muted)" }}>
                — <span style={{ color: "var(--text-main)", fontWeight: 600 }}>{screenName}</span>
              </span>
            )}
          </div>

          {/* Node View (React Flow) */}
          {centerView === 'node' && (
            <div style={{ flex: 1, position: 'relative' }}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.2}
                maxZoom={2}
              >
                <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--border-color)" />
                <Controls style={{ background: "var(--bg-panel)", fill: "var(--text-main)" }} />
              </ReactFlow>
            </div>
          )}

          {/* Graph View VBA / WPF (Cytoscape) */}
          {(centerView === 'graph' || centerView === 'graphWpf') && (
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {screenName ? (
                (() => {
                  const s = filteredSidebarScreens.find(i => i.name === screenName);
                  let actualType: "form" | "report" | "module" | "macro" = "form";
                  if (viewMode === "module") actualType = "module";
                  else if (viewMode === "macro") actualType = "macro";
                  else if (s) {
                    if (s.name.toUpperCase().startsWith("R") || s.type === "report") actualType = "report";
                    else actualType = "form";
                  }
                  const wpf = centerView === "graphWpf";
                  return (
                    <GraphView
                      name={screenName}
                      type={actualType}
                      apiPath={wpf ? "/api/graph-wpf" : "/api/graph"}
                      graphKind={wpf ? "wpf" : "vba"}
                    />
                  );
                })()
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: "var(--text-muted)", gap: '12px' }}>
                  <span style={{ fontSize: 48, opacity: 0.5 }}>{centerView === "graphWpf" ? "◈" : "🕸"}</span>
                  <span style={{ fontSize: '14px' }}>Chọn một Form / Module / Macro từ Task Explorer bên trái</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Global Sidebar with Custom Width Resizer */}
        <div className="terminal-sidebar" style={{ width: sidebarWidth }}>
          <div className="sidebar-resizer" onMouseDown={() => { isResizing.current = true; }} />
          
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', backgroundColor: '#151822' }}>
            <div 
              style={{ padding: '10px 14px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'logs' ? '#10b981' : "var(--text-muted)", borderBottom: activeTab === 'logs' ? '2px solid #10b981' : '2px solid transparent' }}
              onClick={() => setActiveTab('logs')}
            >
              <Terminal size={13} /> System Log
            </div>
            <div 
              style={{ padding: '10px 14px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'preview' ? '#f59e0b' : "var(--text-muted)", borderBottom: activeTab === 'preview' ? '2px solid #f59e0b' : '2px solid transparent' }}
              onClick={() => setActiveTab('preview')}
            >
              <DatabaseZap size={13} /> DB Preview
            </div>
            <div 
              style={{ padding: '10px 14px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', color: activeTab === 'tokens' ? '#a855f7' : "var(--text-muted)", borderBottom: activeTab === 'tokens' ? '2px solid #a855f7' : '2px solid transparent', position: 'relative' }}
              onClick={() => setActiveTab('tokens')}
            >
              <BarChart2 size={13} /> Token Stats
              {(tokenStats || ddTokenStats) && (
                <span style={{ position: 'absolute', top: 6, right: 4, width: 7, height: 7, borderRadius: '50%', background: '#a855f7' }} />
              )}
            </div>
          </div>

          {activeTab === "logs" && (
            <div className="terminal-content" style={{ overflowY: 'auto', flex: 1, padding: 0 }}>
              <div style={{ padding: '16px' }}>
                {systemLogs.map((log, i) => (
                  <div key={i} className="log-line">
                    <span className="log-time">[{log.time}]</span>
                    <span style={{ color: getLogColor(log.level), fontWeight: 'bold' }}>[{log.level}]</span>
                    <span style={{ marginLeft: 6, color: "var(--text-main)" }}>{log.message}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}

          {activeTab === "tokens" && (
            <div style={{ overflowY: 'auto', flex: 1, padding: '16px' }}>
              {/* Header + Download button */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <span style={{ color: '#a855f7', fontWeight: 700, fontSize: 13 }}>📊 Token Usage Report</span>
                <a
                  href="/api/download-token-report"
                  download
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', background: 'rgba(168,85,247,0.15)', color: '#c084fc', border: '1px solid #7c3aed', borderRadius: 6, fontSize: 12, fontWeight: 600, textDecoration: 'none', cursor: 'pointer' }}
                >
                  <Download size={13} /> Download Excel
                </a>
              </div>

              {/* BD Stats */}
              {tokenStats && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ color: '#3b82f6', fontWeight: 700, fontSize: 12, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    🔵 BD Agent
                    <span style={{ background: 'rgba(59,130,246,0.15)', padding: '2px 8px', borderRadius: 10, color: '#60a5fa' }}>
                      {tokenStats.total_tokens.toLocaleString()} tokens
                    </span>
                    <span style={{ background: 'rgba(16,185,129,0.15)', padding: '2px 8px', borderRadius: 10, color: '#34d399' }}>
                      ${tokenStats.total_cost_usd.toFixed(5)}
                    </span>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead>
                      <tr style={{ background: '#1a1f2e' }}>
                        {['Item', 'Model', 'Stage', 'Input', 'Output', 'Cost $'].map(h => (
                          <th key={h} style={{ padding: '5px 6px', textAlign: 'left', color: "var(--text-muted)", fontWeight: 600, borderBottom: '1px solid #2d3347' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tokenStats.records.map((r, i) => (
                        <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : "var(--bg-dark)" }}>
                          <td style={{ padding: '4px 6px', color: "var(--text-main)", maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.item}>{r.item}</td>
                          <td style={{ padding: '4px 6px', color: '#93c5fd', fontSize: 10 }}>{r.model}</td>
                          <td style={{ padding: '4px 6px', color: '#fbbf24', fontSize: 10 }}>{r.stage}</td>
                          <td style={{ padding: '4px 6px', color: '#a5b4fc', textAlign: 'right' }}>{r.input_tokens.toLocaleString()}</td>
                          <td style={{ padding: '4px 6px', color: '#86efac', textAlign: 'right' }}>{r.output_tokens.toLocaleString()}</td>
                          <td style={{ padding: '4px 6px', color: '#f9a8d4', textAlign: 'right' }}>{r.cost_usd.toFixed(5)}</td>
                        </tr>
                      ))}
                      <tr style={{ background: '#0d1a0f', borderTop: '1px solid #166534' }}>
                        <td colSpan={3} style={{ padding: '5px 6px', color: '#34d399', fontWeight: 700, fontSize: 11 }}>TỔNG</td>
                        <td style={{ padding: '5px 6px', color: '#a5b4fc', textAlign: 'right', fontWeight: 700 }}>{tokenStats.records.reduce((s,r)=>s+r.input_tokens,0).toLocaleString()}</td>
                        <td style={{ padding: '5px 6px', color: '#86efac', textAlign: 'right', fontWeight: 700 }}>{tokenStats.records.reduce((s,r)=>s+r.output_tokens,0).toLocaleString()}</td>
                        <td style={{ padding: '5px 6px', color: '#f9a8d4', textAlign: 'right', fontWeight: 700 }}>${tokenStats.total_cost_usd.toFixed(5)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* DD Stats */}
              {ddTokenStats && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ color: '#f97316', fontWeight: 700, fontSize: 12, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    🟠 DD Agent
                    <span style={{ background: 'rgba(249,115,22,0.15)', padding: '2px 8px', borderRadius: 10, color: '#fb923c' }}>
                      {ddTokenStats.total_tokens.toLocaleString()} tokens
                    </span>
                    <span style={{ background: 'rgba(16,185,129,0.15)', padding: '2px 8px', borderRadius: 10, color: '#34d399' }}>
                      ${ddTokenStats.total_cost_usd.toFixed(5)}
                    </span>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead>
                      <tr style={{ background: '#1a1f2e' }}>
                        {['Item', 'Model', 'Stage', 'Input', 'Output', 'Cost $'].map(h => (
                          <th key={h} style={{ padding: '5px 6px', textAlign: 'left', color: "var(--text-muted)", fontWeight: 600, borderBottom: '1px solid #2d3347' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ddTokenStats.records.map((r, i) => (
                        <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : "var(--bg-dark)" }}>
                          <td style={{ padding: '4px 6px', color: "var(--text-main)", maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.item}>{r.item}</td>
                          <td style={{ padding: '4px 6px', color: '#93c5fd', fontSize: 10 }}>{r.model}</td>
                          <td style={{ padding: '4px 6px', color: '#fbbf24', fontSize: 10 }}>{r.stage}</td>
                          <td style={{ padding: '4px 6px', color: '#a5b4fc', textAlign: 'right' }}>{r.input_tokens.toLocaleString()}</td>
                          <td style={{ padding: '4px 6px', color: '#86efac', textAlign: 'right' }}>{r.output_tokens.toLocaleString()}</td>
                          <td style={{ padding: '4px 6px', color: '#f9a8d4', textAlign: 'right' }}>{r.cost_usd.toFixed(5)}</td>
                        </tr>
                      ))}
                      <tr style={{ background: '#0d1a0f', borderTop: '1px solid #166534' }}>
                        <td colSpan={3} style={{ padding: '5px 6px', color: '#34d399', fontWeight: 700, fontSize: 11 }}>TỔNG</td>
                        <td style={{ padding: '5px 6px', color: '#a5b4fc', textAlign: 'right', fontWeight: 700 }}>{ddTokenStats.records.reduce((s,r)=>s+r.input_tokens,0).toLocaleString()}</td>
                        <td style={{ padding: '5px 6px', color: '#86efac', textAlign: 'right', fontWeight: 700 }}>{ddTokenStats.records.reduce((s,r)=>s+r.output_tokens,0).toLocaleString()}</td>
                        <td style={{ padding: '5px 6px', color: '#f9a8d4', textAlign: 'right', fontWeight: 700 }}>${ddTokenStats.total_cost_usd.toFixed(5)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* Grand total if both exist */}
              {tokenStats && ddTokenStats && (() => {
                const gt = tokenStats.total_tokens + ddTokenStats.total_tokens;
                const gc = tokenStats.total_cost_usd + ddTokenStats.total_cost_usd;
                return (
                  <div style={{ border: '1px solid #374151', borderRadius: 8, padding: '10px 14px', background: '#0f172a', marginTop: 4 }}>
                    <div style={{ color: '#e2e8f0', fontWeight: 700, fontSize: 12, marginBottom: 4 }}>🔢 Grand Total (BD + DD)</div>
                    <div style={{ display: 'flex', gap: 20 }}>
                      <span style={{ color: '#a5b4fc' }}>Tokens: <strong style={{ color: '#fff' }}>{gt.toLocaleString()}</strong></span>
                      <span style={{ color: '#f9a8d4' }}>Chi phí: <strong style={{ color: '#34d399' }}>${gc.toFixed(5)}</strong></span>
                    </div>
                  </div>
                );
              })()}

              {!tokenStats && !ddTokenStats && (
                <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                  <BarChart2 size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
                  Chưa có dữ liệu. Hãy chạy BD Agent hoặc DD Agent.
                </div>
              )}

              {lastLogFile && (
                <div style={{ marginTop: 16, padding: '8px 12px', background: "var(--bg-dark)", borderRadius: 6, border: '1px solid #1d4ed8', fontSize: 11, color: '#93c5fd' }}>
                  📁 Log file: <span style={{ color: '#60a5fa', wordBreak: 'break-all' }}>{lastLogFile}</span>
                </div>
              )}
            </div>
          )}

          {activeTab === "preview" && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '16px', overflowY: 'auto' }}>
              {dbData ? (
                <div style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ color: '#f59e0b', fontSize: '13px', fontWeight: 'bold' }}>
                      Cấu trúc AST {previewMode === "jsonl" ? "(JSONL Mode)" : "đẩy vào LLM"} 
                      <span style={{ color: '#34d399', margin: '0 6px', padding: '2px 6px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '4px' }}>
                        ~{Math.ceil(fullJsonString.length / 4).toLocaleString()} Tokens
                      </span>
                      <span style={{ color: '#ec4899', margin: '0 6px', padding: '2px 6px', background: 'rgba(236, 72, 153, 0.1)', borderRadius: '4px' }} title="Giá xử lý ước tính dựa trên 0.15$ / 1 Triệu Tokens (Tương đương chuẩn Fast LLMs)">
                        Chi phí: {((Math.ceil(fullJsonString.length / 4) / 1000000) * 0.15).toFixed(5)} $
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        onClick={() => setPreviewMode("json")}
                        style={{ padding: '6px 8px', background: previewMode === 'json' ? '#3b82f6' : 'rgba(59, 130, 246, 0.2)', color: previewMode === 'json' ? '#fff' : '#60a5fa', border: '1px solid #3b82f6', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                        View JSON
                      </button>
                      <button 
                        onClick={() => setPreviewMode("jsonl")}
                        style={{ padding: '6px 8px', background: previewMode === 'jsonl' ? '#10b981' : 'rgba(16, 185, 129, 0.2)', color: previewMode === 'jsonl' ? '#fff' : '#34d399', border: '1px solid #10b981', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                        View JSONL
                      </button>
                      
                      {dbData?.macro?.raw_xml && (
                        <button 
                          onClick={() => setPreviewMode("xml")}
                          style={{ padding: '6px 8px', background: previewMode === 'xml' ? '#eab308' : 'rgba(234, 179, 8, 0.2)', color: previewMode === 'xml' ? '#fff' : '#facc15', border: '1px solid #eab308', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>
                          View XML
                        </button>
                      )}
                      
                      <div style={{ width: '1px', background: "var(--border-color)", margin: '0 4px' }} />
                      
                      <button 
                        onClick={handleCopyJson}
                        style={{ padding: '6px 12px', background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', border: '1px solid #3b82f6', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {copyStatus === "json" ? "✅ Đã Copy!" : "📋 Copy JSON"}
                      </button>
                      <button 
                        onClick={handleCopyJsonL}
                        style={{ padding: '6px 12px', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', border: '1px solid #10b981', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                        title="Đóng gói JSONL (Newline-Delimited JSON) để Fine-tuning hoặc RAG">
                        {copyStatus === "jsonl" ? "✅ Đã Copy!" : "🧩 Convert to JSONL"}
                      </button>
                    </div>
                  </div>
                  <textarea 
                    style={{ 
                      fontFamily: 'monospace', 
                      fontSize: '13px', 
                      color: '#fbbf24', 
                      background: '#291c0a', 
                      padding: '16px', 
                      borderRadius: '6px', 
                      border: '1px solid #451a03', 
                      flex: 1, 
                      resize: 'none',
                      whiteSpace: 'pre',
                      overflowWrap: 'normal',
                      overflowX: 'auto',
                      overflowY: 'auto'
                    }}
                    readOnly
                    value={fullJsonString}
                  />
                </div>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: '13px', textAlign: 'center', marginTop: '40px' }}>
                  <DatabaseZap size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
                  Dữ liệu rỗng. Hãy chạy Node truy vấn MongoDB.
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
