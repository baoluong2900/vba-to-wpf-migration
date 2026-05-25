"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { 
  DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Play, CheckCircle2, Clock, Terminal, FolderOpen, Sparkles
} from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

interface LogEntry {
  time: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' | 'RUNNING';
  message: string;
}

const STEPS = [
  { id: 1, title: 'Initialize Workspace', desc: 'Verify path & connection' },
  { id: 2, title: 'Export JSON', desc: 'Extract Access forms & macros' },
  { id: 3, title: 'AST Parsing', desc: 'Convert raw VBA/UI to JSON' },
  { id: 4, title: 'Seed MongoDB', desc: 'Upsert into vba_brain core' },
  { id: 5, title: 'Complete', desc: 'Ready for Layer 2 Workflow' },
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
      const response = await fetch('/api/v1/layer1/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_path: dbPath })
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

  const getLogColor = (level: string) => {
    if (level === 'ERROR') return '#ef4444';
    if (level === 'SUCCESS') return '#10b981';
    if (level === 'WARN') return '#f59e0b';
    return '#60a5fa'; // INFO
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

      <main className="layout-content" style={{ display: 'flex', justifyContent: 'center', backgroundColor: '#0b0c10', overflowY: 'auto', padding: '40px 24px' }}>
        
        {/* Centered Single Panel Workspace */}
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '960px', gap: '32px' }}>
          
          {/* Main Dashboard Card */}
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            backdropFilter: 'blur(10px)',
            position: 'relative',
            overflow: 'hidden'
          }}>
            {/* Background Light Effect */}
            <div style={{ position: 'absolute', top: '-10%', left: '-10%', width: '30%', height: '40%', borderRadius: '50%', background: 'rgba(59, 130, 246, 0.08)', filter: 'blur(50px)', pointerEvents: 'none' }} />
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '28px' }}>
              <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'linear-gradient(135deg, #3b82f6, #06b6d4)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 20px rgba(59,130,246,0.3)' }}>
                <DatabaseZap size={22} color="#fff" />
              </div>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#fff', margin: 0 }}>Access Source Database Extractor</h2>
                <p style={{ fontSize: '12px', color: '#9ca3af', margin: '4px 0 0 0' }}>Verify path and launch extraction to translate database schema and modules into structural representations.</p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center' }}>
                <FolderOpen size={16} style={{ position: 'absolute', left: '14px', color: '#9ca3af' }} />
                <input 
                  type="text" 
                  value={dbPath}
                  onChange={e => setDbPath(e.target.value)}
                  placeholder="Enter Access Database Path (e.g. database.accdb)..."
                  style={{
                    width: '100%',
                    background: 'rgba(0,0,0,0.4)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '8px',
                    padding: '14px 14px 14px 42px',
                    color: '#fff',
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'border-color 0.2s'
                  }}
                />
              </div>
              <button
                onClick={handleStartExtraction}
                disabled={isExtracting}
                style={{
                  padding: '14px 28px',
                  borderRadius: '8px',
                  border: 'none',
                  background: isExtracting ? '#374151' : 'linear-gradient(135deg, #3b82f6, #0284c7)',
                  color: isExtracting ? '#9ca3af' : '#fff',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: isExtracting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: isExtracting ? 'none' : '0 4px 16px rgba(59,130,246,0.3)',
                  transition: 'all 0.3s'
                }}
              >
                {isExtracting ? <Clock size={16} className="animate-spin" /> : <Play size={16} />}
                {isExtracting ? 'Extracting...' : 'Start Extraction'}
              </button>
            </div>
          </div>

          {/* Horizontal Pipeline Steps Timeline */}
          <div style={{
            background: 'rgba(255,255,255,0.01)',
            border: '1px solid rgba(255,255,255,0.03)',
            borderRadius: '16px',
            padding: '24px 32px 32px 32px',
            boxShadow: '0 4px 24px rgba(0,0,0,0.15)'
          }}>
            <h3 style={{ fontSize: '12px', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', marginBottom: '24px', letterSpacing: '0.7px' }}>Extraction Pipeline</h3>
            
            <div style={{ display: 'flex', flexDirection: 'row', gap: '16px', width: '100%' }}>
              {STEPS.map((step, index) => {
                const isCompleted = activeStep > step.id || activeStep === 5;
                const isActive = activeStep === step.id && activeStep !== 5;
                const isLast = index === STEPS.length - 1;
                
                return (
                  <div key={step.id} style={{ 
                    flex: 1,
                    display: 'flex', 
                    flexDirection: 'column',
                    opacity: isExtracting && !isActive && !isCompleted ? 0.4 : 1,
                    transition: 'opacity 0.3s',
                    position: 'relative'
                  }}>
                    {/* Circle Icon and Connecting Line Row */}
                    <div style={{ display: 'flex', alignItems: 'center', width: '100%', marginBottom: '12px' }}>
                      <div style={{ 
                        width: '28px', 
                        height: '28px', 
                        borderRadius: '50%', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        background: isCompleted ? 'rgba(16, 185, 129, 0.1)' : isActive ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255,255,255,0.02)',
                        border: isCompleted ? '1px solid #10b981' : isActive ? '1px solid #3b82f6' : '1px solid rgba(255,255,255,0.08)',
                        zIndex: 2,
                        flexShrink: 0
                      }}>
                        {isCompleted ? (
                          <CheckCircle2 size={14} style={{ color: '#10b981' }} />
                        ) : isActive ? (
                          <Clock size={14} style={{ color: '#3b82f6' }} className="animate-spin" />
                        ) : (
                          <span style={{ fontSize: '11px', color: '#6b7280', fontWeight: 600 }}>{step.id}</span>
                        )}
                      </div>
                      
                      {!isLast && (
                        <div style={{ 
                          flex: 1, 
                          height: '2px', 
                          backgroundColor: isCompleted ? '#10b981' : 'rgba(255,255,255,0.06)',
                          marginLeft: '12px',
                          marginRight: '12px',
                          transition: 'background-color 0.3s'
                        }} />
                      )}
                    </div>
                    
                    {/* Text Details */}
                    <div>
                      <div style={{ 
                        fontSize: '12px', 
                        fontWeight: 600, 
                        color: isActive ? '#fff' : isCompleted ? '#e5e7eb' : '#6b7280',
                        display: 'flex',
                        flexDirection: 'column'
                      }}>
                        {step.title}
                        {isActive && <span style={{ fontSize: '8px', color: '#3b82f6', fontWeight: 700, marginTop: '2px', letterSpacing: '0.5px' }}>EXTRACTING</span>}
                      </div>
                      <div style={{ fontSize: '10px', color: '#4b5563', marginTop: '4px', lineHeight: 1.3 }}>
                        {step.desc}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Log Output Console Card */}
          <div style={{
            background: '#07080c',
            border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: '16px',
            height: '280px',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            boxShadow: '0 4px 24px rgba(0,0,0,0.2)'
          }}>
            <div style={{ height: '44px', backgroundColor: '#11131c', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 600, color: '#fff' }}>
                <Terminal size={14} style={{ color: '#3b82f6' }} /> Logs Output Console
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                {(['all', 'info', 'success', 'error'] as const).map(f => (
                  <button 
                    key={f}
                    onClick={() => setLogFilter(f)}
                    style={{
                      background: logFilter === f ? 'rgba(255,255,255,0.08)' : 'transparent',
                      border: 'none',
                      color: logFilter === f ? '#fff' : '#6b7280',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      textTransform: 'uppercase'
                    }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            
            <div className="terminal-content" style={{ flex: 1, padding: '16px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '12px' }}>
              {logs.length === 0 ? (
                <div style={{ color: '#4b5563', fontStyle: 'italic', textAlign: 'center', marginTop: '60px' }}>No logs outputted. Click &quot;Start Extraction&quot; to run the parser pipeline.</div>
              ) : (
                filteredLogs.map((log, idx) => (
                  <div key={idx} className="log-line" style={{ display: 'flex', gap: '8px', color: getLogColor(log.level) }}>
                    <span className="log-time" style={{ color: '#4b5563' }}>[{log.time}]</span>
                    <span style={{ fontWeight: 600 }}>[{log.level}]</span>
                    <span style={{ color: '#e5e7eb' }}>{log.message}</span>
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
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
      `}} />
    </>
  );
}
