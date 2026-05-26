"use client";

import { useState, useEffect, useRef } from "react";
import { 
  DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Play, CheckCircle2, Clock, Terminal, FolderOpen, Sparkles, AlertCircle
} from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

interface LogEntry {
  time: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' | 'RUNNING';
  message: string;
}

const STEPS = [
  { id: 1, title: 'Initialize Workspace', desc: 'Verify paths & DB connections' },
  { id: 2, title: 'Export JSON', desc: 'Extract Access forms & macros' },
  { id: 3, title: 'AST Parsing', desc: 'Convert raw VBA/UI to structured JSON' },
  { id: 4, title: 'Seed MongoDB', desc: 'Upsert into vba_brain core' },
  { id: 5, title: 'Extraction Complete', desc: 'Ready for Layer 2 Intelligence' },
];

export default function Layer1Parser() {
  const [isExtracting, setIsExtracting] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [dbPath, setDbPath] = useState("legacy_db.accdb");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<'all' | 'info' | 'success' | 'error'>('all');

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Add a log to the terminal console
  const addLog = (level: LogEntry['level'], message: string) => {
    const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });
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
                addLog("SUCCESS", "Layer 1 Source Extraction completed successfully! Data seeded into MongoDB.");
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

      <main className="flex-1 flex justify-center items-start overflow-y-auto bg-[var(--bg-dark)] py-12 px-6 relative min-h-[calc(100vh-120px)] w-full">
        {/* Animated Background Mesh & Orbs */}
        <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.02)_1px,transparent_1px)] dark:bg-[radial-gradient(rgba(255,255,255,0.015)_1.5px,transparent_1.5px)] [background-size:24px_24px] pointer-events-none" />
        <div className="absolute top-[5%] left-[10%] w-[500px] h-[500px] rounded-full bg-indigo-500/10 dark:bg-indigo-500/5 blur-[120px] pointer-events-none -z-10 animate-pulse duration-[8000ms]" />
        <div className="absolute bottom-[5%] right-[10%] w-[600px] h-[600px] rounded-full bg-purple-500/10 dark:bg-purple-500/5 blur-[150px] pointer-events-none -z-10 animate-pulse duration-[12000ms]" />

        <div className="flex flex-col w-full max-w-5xl gap-10 relative z-10">
          

          {/* Main Dashboard Control Panel */}
          <div className="bg-white/40 dark:bg-[#151722]/60 backdrop-blur-xl border border-neutral-200 dark:border-white/5 rounded-2xl p-6 shadow-lg transition-all duration-300 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
            
            <div className="flex items-center gap-4 mb-6">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md flex-shrink-0">
                <DatabaseZap size={20} className="text-white" />
              </div>
              <div>
                <h2 className="text-base font-bold text-neutral-900 dark:text-white">Source Database Configuration</h2>
                <p className="text-xs text-neutral-500 dark:text-gray-400 mt-0.5">Specify absolute path to the legacy `.accdb` file.</p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 items-stretch">
              <div className="flex-1 relative flex items-center">
                <FolderOpen size={16} className="absolute left-4 text-neutral-400 focus-within:text-indigo-500 transition-colors" />
                <input 
                  type="text" 
                  value={dbPath}
                  onChange={e => setDbPath(e.target.value)}
                  placeholder="e.g. C:/Projects/legacy_db.accdb"
                  className="w-full bg-white dark:bg-[#0b0c10] border border-neutral-300 dark:border-neutral-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 rounded-xl py-3 pl-11 pr-4 text-neutral-900 dark:text-white text-sm outline-none transition-all duration-200 placeholder-neutral-400 font-mono"
                />
              </div>
              <button
                onClick={handleStartExtraction}
                disabled={isExtracting}
                className={`px-6 py-3 rounded-xl font-bold text-sm transition-all duration-200 flex items-center justify-center gap-2 select-none active:scale-[0.98] ${
                  isExtracting 
                    ? 'bg-neutral-200 dark:bg-neutral-800 text-neutral-500 border border-neutral-300 dark:border-neutral-700 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 cursor-pointer'
                }`}
              >
                {isExtracting ? (
                  <>
                    <Clock size={16} className="animate-spin" />
                    <span>Extracting...</span>
                  </>
                ) : (
                  <>
                    <Play size={16} className="fill-current" />
                    <span>Start Extraction</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Fully Animated Workflow Pipeline */}
          <div className="bg-white/50 dark:bg-slate-900/20 backdrop-blur-lg border border-neutral-200/50 dark:border-white/5 rounded-3xl p-8 md:p-10 shadow-xl relative overflow-hidden animate-fade-in-up" style={{ animationDelay: '200ms' }}>
            <div className="flex items-center justify-between mb-10">
              <h3 className="text-sm font-extrabold text-neutral-700 dark:text-gray-300 uppercase tracking-widest drop-shadow-sm flex items-center gap-2">
                <Cpu size={16} className="text-indigo-500" />
                Execution Pipeline
              </h3>
              {isExtracting && (
                <div className="inline-flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-500/10 border border-indigo-500/20 px-3 py-1 rounded-full shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
                  </span>
                  Processing Data...
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-5 gap-8 md:gap-4 w-full relative">
              {STEPS.map((step, index) => {
                const isCompleted = activeStep > step.id || activeStep === 5;
                const isActive = activeStep === step.id && activeStep !== 5;
                const isLast = index === STEPS.length - 1;
                
                return (
                  <div 
                    key={step.id} 
                    className={`flex md:flex-col items-start md:items-center text-left md:text-center gap-4 md:gap-5 transition-all duration-500 relative ${
                      isExtracting && !isActive && !isCompleted ? 'opacity-40 grayscale-[50%]' : 'opacity-100 grayscale-0'
                    }`}
                  >
                    {/* Circle and Line Row */}
                    <div className="flex items-center w-full relative justify-center md:justify-center">
                      
                      {/* Animated Step Circle */}
                      <div className="relative">
                        {/* Outer Glow Ping for Active */}
                        {isActive && (
                          <div className="absolute inset-0 rounded-full bg-indigo-500/30 animate-ping shadow-[0_0_20px_rgba(99,102,241,0.5)]" />
                        )}
                        {/* Circle body */}
                        <div 
                          className={`relative w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all duration-500 z-10 flex-shrink-0 ${
                            isCompleted 
                              ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-500 text-emerald-600 dark:text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)]'
                              : isActive 
                                ? 'bg-indigo-50 dark:bg-indigo-600/20 border-indigo-500 text-indigo-600 dark:text-indigo-400 shadow-[0_0_30px_rgba(99,102,241,0.5)] scale-110'
                                : 'bg-neutral-100 dark:bg-slate-900/80 border-neutral-300 dark:border-white/10 text-neutral-400 dark:text-gray-500 shadow-inner'
                          }`}
                        >
                          {isCompleted ? (
                            <CheckCircle2 size={22} className="text-emerald-600 dark:text-emerald-400 drop-shadow-sm" />
                          ) : isActive ? (
                            <Clock size={20} className="text-indigo-600 dark:text-indigo-400 animate-spin" />
                          ) : (
                            <span className="text-sm font-black">{step.id}</span>
                          )}
                        </div>
                      </div>
                      
                      {/* Connecting Flowing Pipeline */}
                      {!isLast && (
                        <div className="hidden md:block absolute left-[55%] right-[-45%] top-1/2 -translate-y-1/2 h-[3px] -z-0">
                          {/* Background static line */}
                          <div className="w-full h-full bg-neutral-200 dark:bg-white/10 rounded-full shadow-inner" />
                          {/* Active / Completed progress gradient fill */}
                          <div 
                            className={`absolute inset-y-0 left-0 transition-all duration-1000 ease-in-out rounded-full ${
                              isCompleted 
                                ? 'w-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' 
                                : isActive 
                                  ? 'w-[70%] bg-gradient-to-r from-emerald-500 via-indigo-500 to-transparent bg-[length:200%_100%] animate-gradient-x shadow-[0_0_10px_rgba(99,102,241,0.5)]'
                                  : 'w-0'
                            }`}
                          />
                        </div>
                      )}
                    </div>
                    
                    {/* Step Description */}
                    <div className="flex flex-col justify-center">
                      <span 
                        className={`text-sm md:text-xs lg:text-sm font-extrabold tracking-tight transition-colors duration-300 ${
                          isActive 
                            ? 'text-indigo-700 dark:text-white drop-shadow-sm' 
                            : isCompleted 
                              ? 'text-neutral-800 dark:text-slate-200' 
                              : 'text-neutral-400 dark:text-gray-500'
                        }`}
                      >
                        {step.title}
                      </span>
                      <span className="text-[11px] lg:text-xs text-neutral-500 dark:text-gray-400 mt-1.5 leading-relaxed font-medium">
                        {step.desc}
                      </span>
                      {isActive && (
                        <span className="inline-flex md:justify-center text-[10px] text-indigo-600 dark:text-indigo-400 font-black uppercase mt-2 tracking-widest animate-pulse">
                          Processing...
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Premium Glassmorphic Log Console */}
          <div className="bg-white/70 dark:bg-black/60 backdrop-blur-2xl border border-neutral-200/80 dark:border-white/10 rounded-3xl h-[400px] flex flex-col overflow-hidden shadow-2xl dark:shadow-[0_20px_50px_rgba(0,0,0,0.5)] animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            {/* macOS Style Window Header */}
            <div className="h-[52px] bg-neutral-100/80 dark:bg-[#0a0a0f]/80 border-b border-neutral-200/80 dark:border-white/5 flex items-center justify-between px-6 backdrop-blur-sm">
              <div className="flex items-center gap-2.5">
                <div className="w-3.5 h-3.5 rounded-full bg-[#ff5f56] shadow-sm shadow-[#ff5f56]/20 opacity-90 hover:opacity-100 transition-opacity cursor-pointer"></div>
                <div className="w-3.5 h-3.5 rounded-full bg-[#ffbd2e] shadow-sm shadow-[#ffbd2e]/20 opacity-90 hover:opacity-100 transition-opacity cursor-pointer"></div>
                <div className="w-3.5 h-3.5 rounded-full bg-[#27c93f] shadow-sm shadow-[#27c93f]/20 opacity-90 hover:opacity-100 transition-opacity cursor-pointer"></div>
                <span className="ml-4 text-xs font-bold text-neutral-500 dark:text-gray-400 font-mono flex items-center gap-2 select-none">
                  <Terminal size={14} className="text-indigo-600 dark:text-indigo-400" />
                  pipeline_output.log
                </span>
              </div>
              
              {/* Filter pills */}
              <div className="flex gap-2 bg-neutral-200/50 dark:bg-white/5 p-1 rounded-xl">
                {(['all', 'info', 'success', 'error'] as const).map(f => (
                  <button 
                    key={f}
                    onClick={() => setLogFilter(f)}
                    className={`border-none px-4 py-1.5 rounded-lg text-[10px] font-black cursor-pointer transition-all duration-300 uppercase tracking-widest ${
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
                <div className="flex flex-col items-center justify-center h-full text-neutral-400 dark:text-gray-600 gap-3 select-none">
                  <Terminal size={32} className="opacity-50" />
                  <div className="italic text-xs font-medium">System idle. Ready to initialize extraction pipeline.</div>
                </div>
              ) : (
                <div className="flex flex-col gap-2.5">
                  {filteredLogs.map((log, idx) => {
                    let levelStyles = "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20";
                    if (log.level === 'ERROR') levelStyles = "bg-red-100 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20";
                    if (log.level === 'SUCCESS') levelStyles = "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20";
                    if (log.level === 'WARN') levelStyles = "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20";
                    
                    return (
                      <div key={idx} className="flex items-start gap-4 border-b border-neutral-200/50 dark:border-white/[0.03] pb-2 last:border-0 hover:bg-white/50 dark:hover:bg-white/[0.02] px-2 py-1 rounded-lg transition-colors duration-200 group">
                        <span className="text-neutral-400 dark:text-gray-600 bg-white dark:bg-white/5 border border-neutral-200 dark:border-white/10 px-2 py-1 rounded-md text-[10px] font-mono shadow-sm group-hover:text-neutral-600 dark:group-hover:text-gray-400 transition-colors">
                          {log.time}
                        </span>
                        <span className={`px-2 py-1 rounded-md border text-[10px] font-black tracking-widest uppercase shadow-sm ${levelStyles}`}>
                          {log.level}
                        </span>
                        <span className="text-neutral-700 dark:text-slate-200 break-all select-text font-mono flex-1 whitespace-pre-wrap leading-relaxed mt-0.5 font-medium">
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

      <style dangerouslySetInnerHTML={{__html: `
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        .animate-gradient-x {
          background-size: 200% 100%;
          animation: gradient-x 2s ease infinite;
        }
        @keyframes gradient-x {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        
        .animate-fade-in-up {
          animation: fade-in-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          opacity: 0;
          transform: translateY(20px);
        }
        @keyframes fade-in-up {
          to { opacity: 1; transform: translateY(0); }
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(156, 163, 175, 0.3);
          border-radius: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(156, 163, 175, 0.5);
        }
        
        .dark .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
        }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.2);
        }
      `}} />
    </>
  );
}
