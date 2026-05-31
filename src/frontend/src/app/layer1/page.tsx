"use client";

import { useState, useEffect, useRef } from "react";
import { 
  DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Play, CheckCircle2, Clock, Terminal, FolderOpen, Sparkles, AlertCircle,
  FileCode, Layers, Info, Check, Server
} from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import { LogEntry, formatLogTime } from "../../lib/logging";

const STEPS = [
  { id: 1, title: 'Initialize Workspace', desc: 'Verify paths & DB connections' },
  { id: 2, title: 'AST UI Parsing', desc: 'Convert raw VBA/UI to structured JSON' },
  { id: 3, title: 'Reference Mapping', desc: 'Build macro/module cross-references' },
  { id: 4, title: 'MongoDB Ingestion', desc: 'Seed variables into MongoDB core' },
  { id: 5, title: 'Migration Complete', desc: 'Generate BD/DD & PostgreSQL schemas' },
];

export default function Layer1Parser() {
  const [isExtracting, setIsExtracting] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [dbPath, setDbPath] = useState("src/vba/vba_source");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<'all' | 'info' | 'success' | 'error'>('all');

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Add a log to the terminal console
  const addLog = (level: LogEntry['level'], message: string) => {
    const time = formatLogTime();
    setLogs(prev => [...prev, { time, level, message }]);
    console.log(`[${level}] ${message}`);
  };

  // Scroll terminal logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleStartExtraction = async () => {
    if (isExtracting) return;
    setIsExtracting(true);
    setActiveStep(1);
    setLogs([]);
    addLog("INFO", `Initializing Source Extraction for: ${dbPath}`);

    try {
      const response = await fetch(`/api/v1/layer1/extract?source_path=${encodeURIComponent(dbPath)}`, {
        method: 'GET'
      });

      if (!response.body) throw new Error("No response body received from server");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split('\n').filter(Boolean);
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'log') {
                addLog(data.level as any, data.message);
                if (data.step) {
                  setActiveStep(data.step);
                }
              } else if (data.type === 'error') {
                addLog("ERROR", data.message);
              } else if (data.type === 'done') {
                setActiveStep(5);
                addLog("SUCCESS", "Pipeline completed successfully! BD/DD specs generated & PostgreSQL tables migrated.");
              }
            } catch (e) {
              console.error("Failed to parse SSE", e);
            }
          }
        }
      }
    } catch (err: any) {
      addLog("ERROR", `Extraction failed: ${err.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const filteredLogs = logs.filter(log => {
    if (logFilter === 'all') return true;
    if (logFilter === 'info') return log.level === 'INFO';
    if (logFilter === 'success') return log.level === 'SUCCESS';
    if (logFilter === 'error') return log.level === 'ERROR';
    return true;
  });

  return (
    <>
      <Header />

      <main className="flex-1 flex justify-center items-start overflow-y-auto bg-[var(--bg-dark)] py-12 px-4 sm:px-8 relative w-full min-h-0">
        {/* Animated Background Mesh & Glow Orbs */}
        <div className="ws-mesh" />
        <div className="ws-glow ws-glow-tl" />
        <div className="ws-glow ws-glow-br" />

        <div className="flex flex-col w-full max-w-5xl gap-8 relative z-10">
          
          {/* Header Description Title */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200 dark:border-white/5 pb-6 animate-fade-in-up" style={{ animationDelay: '50ms' }}>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-neutral-900 dark:text-white flex items-center gap-3">
                <DatabaseZap className="text-indigo-500" />
                <span>Layer 1: <span className="ws-gradient-text">Data Ingestion & AST Parser</span></span>
              </h1>
              <p className="text-sm text-neutral-500 dark:text-gray-400 mt-2 max-w-2xl leading-relaxed">
                Ingest legacy Access components (VBA scripts, UI forms, schemas) into MongoDB collections and automatically orchestrate the downstream modernization pipeline.
              </p>
            </div>
            {isExtracting && (
              <div className="inline-flex items-center gap-3 px-4 py-2 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400 font-bold text-sm shadow-[0_0_20px_rgba(99,102,241,0.2)] animate-pulse">
                <Server size={16} className="animate-spin" />
                Orchestrator Executing...
              </div>
            )}
          </div>

          {/* Execution Steps pipeline */}
          <div className="w-full animate-fade-in-up" style={{ animationDelay: '100ms' }}>
            <h3 className="text-xs font-black text-neutral-600 dark:text-gray-400 uppercase tracking-widest mb-6 flex items-center gap-3 px-2">
              <Cpu size={14} className="text-indigo-500" />
              Orchestrator Execution Pipeline
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-5 gap-6 md:gap-4 relative">
              {STEPS.map((step, index) => {
                const isCompleted = activeStep > step.id || activeStep === 5;
                const isActive = activeStep === step.id && activeStep !== 5;
                
                return (
                  <div 
                    key={step.id} 
                    className={`flex flex-col items-center text-center gap-4 transition-all duration-300 p-5 md:p-6 rounded-3xl relative border shadow-sm ${
                      isActive 
                        ? 'bg-indigo-500/10 border-indigo-500/30 ring-4 ring-indigo-500/5 z-10' 
                        : isCompleted 
                          ? 'bg-emerald-500/10 border-emerald-500/30 shadow-sm shadow-emerald-500/5 z-10' 
                          : 'bg-white/40 dark:bg-slate-900/10 border-neutral-200/50 dark:border-white/5 opacity-60'
                    }`}
                  >
                    {/* Connecting line between steps on desktop */}
                    {index < STEPS.length - 1 && (
                      <div className={`hidden md:block absolute top-[40px] left-[calc(50%+20px)] right-[calc(-50%+20px)] h-[2.5px] z-0 transition-all duration-500 ${
                        isCompleted ? 'bg-gradient-to-r from-emerald-500 to-emerald-500' : 
                        activeStep === step.id ? 'bg-gradient-to-r from-indigo-500 to-neutral-200 dark:to-slate-800' :
                        'bg-neutral-200 dark:bg-slate-800'
                      }`} />
                    )}

                    {/* Status Circle */}
                    <div 
                      className={`w-10 h-10 rounded-xl flex items-center justify-center border transition-all duration-300 flex-shrink-0 font-mono text-sm font-black z-10 relative ${
                        isCompleted 
                          ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-500 shadow-sm shadow-emerald-500/10'
                          : isActive 
                            ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-500 shadow-lg shadow-indigo-500/15 animate-pulse'
                            : 'bg-neutral-100 dark:bg-slate-800/80 border-neutral-200 dark:border-white/5 text-neutral-400 dark:text-gray-500'
                      }`}
                    >
                      {isCompleted ? (
                        <Check size={16} className="stroke-[3]" />
                      ) : isActive ? (
                        <Clock size={16} className="animate-spin" />
                      ) : (
                        <span>{step.id}</span>
                      )}
                    </div>

                    {/* Title details */}
                    <div className="flex-1 min-w-0 z-10">
                      <div className="flex flex-col items-center gap-1.5">
                        <span 
                          className={`text-xs font-black tracking-tight transition-colors duration-300 whitespace-nowrap ${
                            isActive 
                              ? 'text-indigo-600 dark:text-white font-extrabold' 
                              : isCompleted 
                                ? 'text-neutral-800 dark:text-slate-200 font-semibold' 
                                : 'text-neutral-400 dark:text-gray-500'
                          }`}
                        >
                          {step.title}
                        </span>
                        {isActive && (
                          <span className="text-[8px] text-indigo-600 dark:text-indigo-400 font-black uppercase tracking-widest bg-indigo-500/10 px-2 py-0.5 rounded-md animate-pulse">
                            Executing
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-neutral-500 dark:text-gray-400 mt-1 leading-normal max-w-[150px] mx-auto">
                        {step.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Centered Minimalist Ingestion Run Button */}
          <div className="flex flex-col items-center justify-center my-4 animate-fade-in-up" style={{ animationDelay: '150ms' }}>
            <button
              onClick={handleStartExtraction}
              disabled={isExtracting}
              className={`px-12 py-4.5 rounded-2xl font-black text-base transition-all duration-300 flex items-center justify-center gap-4 select-none active:scale-[0.97] cursor-pointer shadow-lg hover:shadow-xl ${
                isExtracting 
                  ? 'bg-gradient-to-r from-indigo-600/50 to-purple-600/50 text-white/70 border border-indigo-500/20 cursor-not-allowed shadow-inner animate-pulse'
                  : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white border border-indigo-400/25 shadow-indigo-500/20 hover:shadow-indigo-500/35'
              }`}
            >
              {isExtracting ? (
                <>
                  <Clock size={20} className="animate-spin text-white" />
                  <span>INGESTING WORKSPACE...</span>
                </>
              ) : (
                <>
                  <Play size={20} className="fill-current drop-shadow-md" />
                  <span>START PIPELINE INGESTION</span>
                </>
              )}
            </button>
            <p className="text-[10px] text-neutral-500 dark:text-gray-500 mt-3 font-semibold uppercase tracking-wider select-none">
              Source Location: <code className="font-mono bg-neutral-200/50 dark:bg-white/5 px-2 py-0.5 rounded text-neutral-600 dark:text-gray-400">{dbPath}</code>
            </p>
          </div>

          {/* Premium Glassmorphic Log Console */}
          <div className="bg-white/70 dark:bg-black/60 backdrop-blur-2xl border-t border-white/40 dark:border-white/10 rounded-3xl h-[400px] flex flex-col overflow-hidden shadow-xl dark:shadow-[0_20px_50px_rgba(0,0,0,0.5)] animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            
            {/* macOS Window Header */}
            <div className="h-[52px] bg-neutral-100/80 dark:bg-[var(--bg-terminal)]/80 border-b border-neutral-200/80 dark:border-white/5 flex items-center justify-between px-6 backdrop-blur-sm">
              <div className="flex items-center gap-3.5">
                <div className="w-3 h-3 rounded-full bg-[#ff5f56] opacity-90"></div>
                <div className="w-3 h-3 rounded-full bg-[#ffbd2e] opacity-90"></div>
                <div className="w-3 h-3 rounded-full bg-[#27c93f] opacity-90"></div>
                <span className="ml-4 text-xs font-black text-neutral-500 dark:text-gray-400 font-mono flex items-center gap-3 select-none tracking-wider uppercase">
                  <Terminal size={14} className="text-indigo-600 dark:text-indigo-400" />
                  pipeline_output.log
                </span>
              </div>
              
              {/* Filter pills */}
              <div className="flex gap-2.5 bg-neutral-200/50 dark:bg-white/5 p-1 rounded-xl">
                {(['all', 'info', 'success', 'error'] as const).map(f => (
                  <button 
                    key={f}
                    onClick={() => setLogFilter(f)}
                    className={`border-none px-3.5 py-1 rounded-lg text-[10px] font-black cursor-pointer transition-all duration-300 uppercase tracking-widest ${
                      logFilter === f 
                        ? 'bg-white dark:bg-neutral-800 text-indigo-600 dark:text-white shadow-sm' 
                        : 'bg-transparent text-neutral-500 dark:text-gray-500 hover:text-neutral-800 dark:hover:text-gray-300'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Output log body */}
            <div className="flex-1 p-6 overflow-y-auto font-mono text-xs leading-relaxed custom-scrollbar bg-neutral-50/50 dark:bg-transparent">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-neutral-400 dark:text-gray-600 gap-4 select-none">
                  <Terminal size={32} className="opacity-50 animate-pulse duration-[3000ms]" />
                  <div className="italic text-xs font-semibold uppercase tracking-wider">System Idle. Waiting for ingestion run.</div>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {filteredLogs.map((log, idx) => {
                    let levelStyles = "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20";
                    if (log.level === 'ERROR') levelStyles = "bg-red-100 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20";
                    if (log.level === 'SUCCESS') levelStyles = "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20";
                    if (log.level === 'WARN') levelStyles = "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20";
                    
                    return (
                      <div key={idx} className="flex items-start gap-3 border-b border-neutral-200/40 dark:border-white/[0.02] pb-2 last:border-0 hover:bg-white/40 dark:hover:bg-white/[0.01] px-2 py-1.5 rounded-lg transition-colors duration-200 group">
                        <span className="text-neutral-400 dark:text-gray-600 bg-white dark:bg-white/5 border border-neutral-200 dark:border-white/10 px-2 py-0.5 rounded-md text-[10px] font-mono shadow-sm group-hover:text-neutral-600 dark:group-hover:text-gray-400 transition-colors">
                          {log.time}
                        </span>
                        <span className={`px-2 py-0.5 rounded-md border text-[10px] font-black tracking-widest uppercase shadow-sm ${levelStyles}`}>
                          {log.level}
                        </span>
                        <span className="text-neutral-700 dark:text-slate-200 break-all select-text font-mono flex-1 whitespace-pre-wrap leading-relaxed font-semibold">
                          {log.message}
                        </span>
                      </div>
                    );
                  })}
                  <div ref={logsEndRef} className="h-4" />
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
