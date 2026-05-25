"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { 
  ArrowRight, DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Sparkles, ChevronRight, CheckCircle2, RefreshCw, Terminal, Play
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";

// Scroll reveal component using Intersection Observer
function RevealOnScroll({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(40px)",
        transition: `opacity 1.2s cubic-bezier(0.16, 1, 0.3, 1) ${delay}ms, transform 1.2s cubic-bezier(0.16, 1, 0.3, 1) ${delay}ms`
      }}
    >
      {children}
    </div>
  );
}

// Sample codes for the interactive translation playground
const vbaCode = `Public Sub ProcessOrder(OrderId As Long)
    Dim db As Database
    Dim rs As Recordset
    Set db = CurrentDb
    Set rs = db.OpenRecordset( _
        "SELECT * FROM Orders WHERE ID = " & OrderId)
    If Not rs.EOF Then
        MsgBox "Processing: " & rs("CustName")
    End If
    rs.Close
End Sub`;

const csharpCode = `public async Task ProcessOrderAsync(long orderId)
{
    using var db = new VbaBrainContext();
    var order = await db.Orders
        .FirstOrDefaultAsync(o => o.Id == orderId);
        
    if (order != null)
    {
        MessageBox.Show($"Processing: {order.CustName}");
    }
}`;

export default function LandingPage() {
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
  const [isMounted, setIsMounted] = useState(false);

  // Playground states
  const [isConverting, setIsConverting] = useState(false);
  const [isConverted, setIsConverted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Idle");

  useEffect(() => {
    setIsMounted(true);
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  // Run AI conversion simulation
  const handleStartConversion = () => {
    if (isConverting) return;
    setIsConverting(true);
    setIsConverted(false);
    setProgress(0);
    setStatusText("Parsing Access AST...");

    const interval = setInterval(() => {
      setProgress(prev => {
        const next = prev + 5;
        if (next <= 25) setStatusText("Parsing Access AST...");
        else if (next <= 60) setStatusText("Mapping Entity & Logic...");
        else if (next <= 85) setStatusText("Synthesizing WPF & C#...");
        else if (next < 100) setStatusText("Validating C# compile...");
        
        if (next >= 100) {
          clearInterval(interval);
          setIsConverting(false);
          setIsConverted(true);
          setStatusText("Done!");
          return 100;
        }
        return next;
      });
    }, 80);
  };

  const handleResetConversion = () => {
    setIsConverting(false);
    setIsConverted(false);
    setProgress(0);
    setStatusText("Idle");
  };

  const steps = [
    {
      id: "Step 1",
      layer: "Layer 1",
      title: "Source Extraction",
      desc: "Deep parses legacy Access databases into structured AST representations.",
      icon: DatabaseZap,
      link: "/layer1",
      gradient: "from-blue-500/20 to-cyan-400/20",
      glowColor: "rgba(56, 189, 248, 0.15)",
      iconColor: "text-cyan-400"
    },
    {
      id: "Step 2",
      layer: "Layer 2",
      title: "Logic Analysis",
      desc: "AI engine maps complex entity relationships to extract core business logic.",
      icon: Bot,
      link: "/layer2",
      gradient: "from-purple-500/20 to-indigo-500/20",
      glowColor: "rgba(168, 85, 247, 0.15)",
      iconColor: "text-purple-400"
    },
    {
      id: "Step 3",
      layer: "Layer 3",
      title: "Excel Documentation",
      desc: "Auto-translates logic into technical Excel specifications for review.",
      icon: FileSpreadsheet,
      link: "/layer3",
      gradient: "from-emerald-400/20 to-teal-500/20",
      glowColor: "rgba(52, 211, 153, 0.15)",
      iconColor: "text-emerald-400"
    },
    {
      id: "Step 4",
      layer: "Layer 4",
      title: "SQL Migration",
      desc: "Safely converts Access SQL dialects into optimized Oracle/SQL Server scripts.",
      icon: Database,
      link: "/layer4",
      gradient: "from-amber-400/20 to-orange-500/20",
      glowColor: "rgba(251, 191, 36, 0.15)",
      iconColor: "text-amber-400"
    },
    {
      id: "Step 5",
      layer: "Layer 5",
      title: "C# & WPF Generation",
      desc: "Synthesizes modern WPF UI components and C# logic to finalize migration.",
      icon: Cpu,
      link: "/layer5",
      gradient: "from-rose-400/20 to-red-500/20",
      glowColor: "rgba(244, 63, 94, 0.15)",
      iconColor: "text-rose-400"
    }
  ];

  return (
    <div className="flex-1 w-full h-full overflow-y-auto bg-[#050506] text-gray-200 font-sans selection:bg-indigo-500/30 selection:text-white relative scroll-smooth">
      <style>{`
        @keyframes shimmer {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes pulse-slow {
          0%, 100% { opacity: 0.4; transform: scale(1) translate(0px, 0px); }
          33% { opacity: 0.6; transform: scale(1.1) translate(30px, -50px); }
          66% { opacity: 0.5; transform: scale(0.9) translate(-20px, 20px); }
        }
        .shimmer-text {
          background-size: 200% auto;
          -webkit-background-clip: text;
          background-clip: text;
          animation: shimmer 6s linear infinite;
        }
        .pulse-bg-1 {
          animation: pulse-slow 15s ease-in-out infinite;
        }
        .pulse-bg-2 {
          animation: pulse-slow 20s ease-in-out infinite alternate;
        }
        .pulse-bg-3 {
          animation: pulse-slow 18s ease-in-out infinite 2s;
        }
        .grid-bg {
          background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
          background-size: 40px 40px;
          background-position: center;
        }
        .radial-fade {
          -webkit-mask-image: radial-gradient(circle at center, black 40%, transparent 80%);
          mask-image: radial-gradient(circle at center, black 40%, transparent 80%);
        }
        .radar-scan {
          background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.2) 50%, transparent 100%);
          background-size: 100% 200px;
          animation: scan 2s linear infinite;
        }
        @keyframes scan {
          0% { background-position: 0 -200px; }
          100% { background-position: 0 400px; }
        }
      `}</style>

      {/* Premium Background Effects */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        {/* Grids */}
        <div className="absolute inset-0 grid-bg radial-fade opacity-70"></div>
        
        {/* Animated Neon Auras */}
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[65%] bg-indigo-600/10 rounded-full blur-[140px] mix-blend-screen pulse-bg-1"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[55%] h-[60%] bg-purple-600/10 rounded-full blur-[140px] mix-blend-screen pulse-bg-2"></div>
        <div className="absolute top-[35%] left-[25%] w-[35%] h-[35%] bg-blue-600/5 rounded-full blur-[120px] mix-blend-screen pulse-bg-3"></div>
      </div>

      {/* Cursor Glow Effect with Inertia */}
      {isMounted && (
        <div 
          style={{
            position: "fixed",
            top: mousePos.y - 200,
            left: mousePos.x - 200,
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0) 70%)",
            pointerEvents: "none",
            zIndex: 2,
            filter: "blur(30px)",
            transition: "top 0.25s cubic-bezier(0.1, 0.8, 0.2, 1), left 0.25s cubic-bezier(0.1, 0.8, 0.2, 1)"
          }}
        />
      )}

      <div className="relative z-10 flex flex-col w-full min-h-full">
        {/* Navbar */}
        <Header />

        <main className="flex-1 flex flex-col w-full">
          {/* Hero Section */}
          <section className="w-full pt-28 pb-16 px-6 relative z-10 flex justify-center">
            <div className="max-w-5xl w-full flex flex-col justify-center items-center text-center">
              <RevealOnScroll delay={0}>
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-sm font-medium mb-10 transition-all duration-500 hover:bg-indigo-500/20 hover:border-indigo-500/30">
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                  Intelligent System Migration
                </div>
              </RevealOnScroll>
              
              <RevealOnScroll delay={150}>
                <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight text-white mb-8 leading-[1.12]">
                  Legacy to Modern in <br className="hidden sm:block" />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 shimmer-text">
                    5 Intelligent Layers
                  </span>
                </h1>
              </RevealOnScroll>
              
              <RevealOnScroll delay={300}>
                <p className="text-lg sm:text-xl text-gray-400/90 max-w-2xl mx-auto mb-12 leading-relaxed font-light">
                  vba_brain is an AI-powered enterprise pipeline that transforms outdated VBA and Access architectures into scalable, modern .NET environments with absolute precision.
                </p>
              </RevealOnScroll>
              
              <RevealOnScroll delay={450}>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mb-12">
                  <Link href="/layer1" className="group relative inline-flex items-center justify-center gap-3 bg-white text-black font-semibold text-lg py-4 px-8 rounded-full overflow-hidden transition-all duration-300 hover:scale-105 hover:shadow-[0_0_35px_rgba(255,255,255,0.25)]">
                    <span>Start Migration</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-300" />
                  </Link>
                  <Link href="#workflow" className="group inline-flex items-center justify-center gap-2 bg-transparent text-gray-300 font-medium text-lg py-4 px-8 rounded-full border border-white/10 hover:bg-white/5 hover:text-white transition-all duration-300 hover:border-white/20">
                    Explore Workflow
                  </Link>
                </div>
              </RevealOnScroll>
            </div>
          </section>

        {/* Metrics Row */}
        <section className="w-full pb-24 relative z-10 flex justify-center">
          <div className="max-w-7xl w-full px-6 sm:px-12">
            <RevealOnScroll>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                {[
                  { value: "10x", label: "Faster Migration", desc: "Reduces rewrite time from months to days", color: "from-blue-400 to-cyan-400" },
                  { value: "99.8%", label: "Code Accuracy", desc: "Automated AST validation checks", color: "from-purple-400 to-indigo-400" },
                  { value: "0", label: "Data Loss Guaranteed", desc: "Strict schema mapping verification", color: "from-emerald-400 to-teal-400" },
                  { value: "100%", label: "Cloud Native", desc: "Clean C# and modern SQL generation", color: "from-amber-400 to-orange-400" }
                ].map((m, i) => (
                  <div key={i} className="bg-white/[0.01] border border-white/5 rounded-2xl p-6 relative overflow-hidden group hover:bg-white/[0.02] hover:border-white/10 transition-all duration-300 hover:-translate-y-1 shadow-lg"
                    style={{ backdropFilter: "blur(8px)" }}>
                    <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-indigo-500 to-transparent"></div>
                    <div className={`text-4xl sm:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r ${m.color} mb-2`}>
                      {m.value}
                    </div>
                    <div className="text-sm font-bold text-gray-200 mb-1">{m.label}</div>
                    <div className="text-xs text-gray-400 font-light leading-relaxed">{m.desc}</div>
                  </div>
                ))}
              </div>
            </RevealOnScroll>
          </div>
        </section>

        {/* Workflow Section */}
        <section id="workflow" className="py-28 px-6 sm:px-12 border-t border-white/5 bg-[#050506]/70 backdrop-blur-sm relative z-10">
          <div className="max-w-7xl mx-auto">
            <RevealOnScroll>
              <div className="flex flex-col items-center text-center mb-24">
                <h2 className="text-3xl sm:text-5xl font-bold text-white mb-6 tracking-tight">The 5-Layer Architecture</h2>
                <p className="text-gray-400 text-lg max-w-2xl font-light">
                  Our meticulously engineered workflow guarantees zero data loss and flawless business logic translation through specialized AI agents.
                </p>
              </div>
            </RevealOnScroll>

            <div className="flex flex-wrap justify-center gap-6">
              {steps.map((step, idx) => {
                const Icon = step.icon;
                return (
                  <RevealOnScroll key={idx} delay={idx * 100}>
                    <Link href={step.link} 
                      className="group relative flex flex-col bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.03] hover:border-white/10 transition-all duration-500 hover:-translate-y-2.5 overflow-hidden no-underline h-full w-full sm:w-[240px] md:w-[220px] lg:w-[200px] xl:w-[220px]"
                      style={{
                        boxShadow: "inset 0 1px 1px rgba(255,255,255,0.02)"
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.boxShadow = `0 12px 30px -10px ${step.glowColor}, inset 0 1px 1px rgba(255,255,255,0.05)`;
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.boxShadow = "inset 0 1px 1px rgba(255,255,255,0.02)";
                      }}
                    >
                      {/* Hover Gradient Overlay */}
                      <div className={`absolute inset-0 bg-gradient-to-br ${step.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none`}></div>
                      
                      <div className="relative z-10 flex flex-col h-full">
                        <div className="text-xs font-bold tracking-[0.2em] text-gray-500 mb-5">{step.layer.toUpperCase()}</div>
                        <div className="w-12 h-12 rounded-2xl bg-white/[0.02] border border-white/5 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-white/10 transition-all duration-500 shadow-md">
                          <Icon className={`w-6 h-6 ${step.iconColor}`} />
                        </div>
                        
                        <h3 className="text-xl font-bold text-gray-100 mb-3 leading-snug group-hover:text-white transition-colors">{step.title}</h3>
                        <p className="text-sm text-gray-400 leading-relaxed font-light flex-1">{step.desc}</p>
                        
                        <div className="mt-8 flex items-center text-sm font-medium text-white/40 group-hover:text-white transition-colors duration-300">
                          Enter Workspace <ChevronRight className="w-4 h-4 ml-1 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300" />
                        </div>
                      </div>
                    </Link>
                  </RevealOnScroll>
                );
              })}
            </div>
          </div>
        </section>

        {/* Detailed 5-Step Timeline Section */}
        <section id="architecture-detail" className="py-32 px-6 sm:px-12 bg-black/40 border-t border-white/5 relative z-10">
          <div className="max-w-5xl mx-auto">
            
            <RevealOnScroll>
              <div className="text-center mb-24">
                <h2 className="text-3xl sm:text-5xl font-bold text-white mb-6 tracking-tight">Detailed 5-Step Pipeline</h2>
                <p className="text-gray-400 text-lg max-w-2xl mx-auto font-light leading-relaxed">
                  See how vba_brain automates the entire migration lifecycle of legacy databases and source code to modern architectures across 5 layers.
                </p>
              </div>
            </RevealOnScroll>

            {/* Vertical Line Container */}
            <div className="relative border-l border-white/10 ml-4 sm:ml-32 pl-8 sm:pl-16 space-y-24 py-10">
              
              {/* Step 1 */}
              <div className="relative group">
                {/* Node icon */}
                <div className="absolute -left-[41px] sm:-left-[73px] w-8 h-8 rounded-full bg-[#050506] border-2 border-cyan-400 flex items-center justify-center shadow-[0_0_15px_rgba(34,211,238,0.3)] group-hover:scale-110 transition-transform duration-300">
                  <DatabaseZap size={14} className="text-cyan-400" />
                </div>
                
                <RevealOnScroll delay={0}>
                  <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] hover:border-cyan-500/10 hover:border-white/10 transition-all duration-500 shadow-xl">
                    <span className="text-xs font-bold text-cyan-400 tracking-[0.2em] uppercase">Step 1 • Layer 1</span>
                    <h3 className="text-2xl font-bold text-white mt-2 mb-4 flex items-center gap-3">
                      Source Extraction <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">Active</span>
                    </h3>
                    
                    <p className="text-sm text-gray-400 leading-relaxed font-light mb-6">
                      The system scans the source Access database file (`.accdb` or `.mdb`). The AI Engine performs a deep structural analysis of schemas (Tables, Relations), UI definitions (Forms, Reports), and legacy VBA macros, translating them into a unified **AST JSON** format.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-[10px] bg-black/40 p-5 rounded-2xl border border-white/5">
                      <div>
                        <div className="text-gray-500 mb-2 font-sans font-bold">Legacy Input (.accdb):</div>
                        <div className="text-red-400">📄 MS Access File</div>
                        <div className="text-gray-400">  └─ Tables: tblOrders</div>
                        <div className="text-gray-400">  └─ UI Form: F_OrderEntry</div>
                        <div className="text-gray-400">  └─ VBA: Form_F_OrderEntry.cls</div>
                      </div>
                      <div className="border-t md:border-t-0 md:border-l border-white/5 pt-3 md:pt-0 md:pl-4">
                        <div className="text-gray-500 mb-2 font-sans font-bold">Structured Output (AST JSON):</div>
                        <div className="text-cyan-300">{"{"}</div>
                        <div className="text-cyan-300">{'  "type": "Form",'}</div>
                        <div className="text-cyan-300">{'  "name": "F_OrderEntry",'}</div>
                        <div className="text-cyan-300">{'  "controls": [{ "type": "TextBox", "name": "txtOrderId" }]'}</div>
                        <div className="text-cyan-300">{"}"}</div>
                      </div>
                    </div>
                  </div>
                </RevealOnScroll>
              </div>

              {/* Step 2 */}
              <div className="relative group">
                <div className="absolute -left-[41px] sm:-left-[73px] w-8 h-8 rounded-full bg-[#050506] border-2 border-purple-400 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.3)] group-hover:scale-110 transition-transform duration-300">
                  <Bot size={14} className="text-purple-400" />
                </div>
                
                <RevealOnScroll delay={0}>
                  <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] hover:border-purple-500/10 hover:border-white/10 transition-all duration-500 shadow-xl">
                    <span className="text-xs font-bold text-purple-400 tracking-[0.2em] uppercase">Step 2 • Layer 2</span>
                    <h3 className="text-2xl font-bold text-white mt-2 mb-4 flex items-center gap-3">
                      Business Logic Analysis <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Active</span>
                    </h3>
                    
                    <p className="text-sm text-gray-400 leading-relaxed font-light mb-6">
                      AI Agents automatically parse the AST syntax tree to map complex data flow relationships (Dependency Graph). This isolates embedded legacy business logic from VBA modules, identifying how UI Forms interact with queries and tables.
                    </p>

                    <div className="p-5 bg-black/40 rounded-2xl border border-white/5 flex flex-col gap-3 font-mono text-[10px] text-gray-400">
                      <div className="text-gray-500 font-sans font-bold">Logic Graph Dependency Mapping:</div>
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="px-2 py-1 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">Form: F_Order</span>
                        <span className="text-gray-600">──►</span>
                        <span className="px-2 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Query: Q_GetOrderDetails</span>
                        <span className="text-gray-600">──►</span>
                        <span className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Table: tblOrders</span>
                      </div>
                      <div className="text-[9px] text-purple-300/80 mt-1">💡 Detection: Form triggers Button_Click event to call query Q_GetOrderDetails and updates CustName column.</div>
                    </div>
                  </div>
                </RevealOnScroll>
              </div>

              {/* Step 3 */}
              <div className="relative group">
                <div className="absolute -left-[41px] sm:-left-[73px] w-8 h-8 rounded-full bg-[#050506] border-2 border-emerald-400 flex items-center justify-center shadow-[0_0_15px_rgba(52,211,153,0.3)] group-hover:scale-110 transition-transform duration-300">
                  <FileSpreadsheet size={14} className="text-emerald-400" />
                </div>
                
                <RevealOnScroll delay={0}>
                  <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] hover:border-emerald-500/10 hover:border-white/10 transition-all duration-500 shadow-xl">
                    <span className="text-xs font-bold text-emerald-400 tracking-[0.2em] uppercase">Step 3 • Layer 3</span>
                    <h3 className="text-2xl font-bold text-white mt-2 mb-4 flex items-center gap-3">
                      Excel Documentation <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Active</span>
                    </h3>
                    
                    <p className="text-sm text-gray-400 leading-relaxed font-light mb-6">
                      Converts database schemas and extracted logic rules into standardized Excel technical specification sheets. This allows engineers to manually inspect, trace, and approve logical mappings before compiling to C#/.NET.
                    </p>

                    <div className="p-5 bg-black/40 rounded-2xl border border-white/5 text-[10px] text-gray-400 overflow-x-auto font-mono">
                      <div className="text-gray-500 mb-3 font-sans font-bold">Generated Excel Spec Sheets:</div>
                      <table className="w-full text-left border-collapse min-w-[400px]">
                        <thead>
                          <tr className="border-b border-white/10 text-gray-400 text-[9px] uppercase">
                            <th className="pb-2">Sheet Name</th>
                            <th className="pb-2">Description</th>
                            <th className="pb-2">Details Count</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="text-emerald-300">
                            <td className="py-2">📊 BD_Specification</td>
                            <td>Database schema specifications</td>
                            <td>12 Tables, 24 Relations</td>
                          </tr>
                          <tr className="text-emerald-300">
                            <td className="py-2">📄 DD_ScreenDefinition</td>
                            <td>UI Form elements and bindings spec</td>
                            <td>8 Forms mapped</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </RevealOnScroll>
              </div>

              {/* Step 4 */}
              <div className="relative group">
                <div className="absolute -left-[41px] sm:-left-[73px] w-8 h-8 rounded-full bg-[#050506] border-2 border-amber-400 flex items-center justify-center shadow-[0_0_15px_rgba(251,191,36,0.3)] group-hover:scale-110 transition-transform duration-300">
                  <Database size={14} className="text-amber-400" />
                </div>
                
                <RevealOnScroll delay={0}>
                  <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] hover:border-amber-500/10 hover:border-white/10 transition-all duration-500 shadow-xl">
                    <span className="text-xs font-bold text-amber-400 tracking-[0.2em] uppercase">Step 4 • Layer 4</span>
                    <h3 className="text-2xl font-bold text-white mt-2 mb-4 flex items-center gap-3">
                      SQL Dialect Conversion <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">Active</span>
                    </h3>
                    
                    <p className="text-sm text-gray-400 leading-relaxed font-light mb-6">
                      Translates proprietary MS Access SQL functions (e.g. `IIf`, `Nz`, `InStr`) into optimized database dialects like Oracle SQL, PostgreSQL, or SQL Server. The conversion agent supports direct schema validation and syntax checks.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-[10px] bg-black/40 p-5 rounded-2xl border border-white/5">
                      <div>
                        <div className="text-gray-500 mb-2 font-sans font-bold">Access SQL (Legacy):</div>
                        <div className="text-amber-400">{"SELECT OrderID, IIf(Status='A', 'Active', 'Inactive') AS State"}</div>
                        <div className="text-amber-400">FROM Orders;</div>
                      </div>
                      <div className="border-t md:border-t-0 md:border-l border-white/5 pt-3 md:pt-0 md:pl-4">
                        <div className="text-gray-500 mb-2 font-sans font-bold">Oracle SQL (Optimized):</div>
                        <div className="text-amber-300">SELECT OrderID,</div>
                        <div className="text-amber-300">{"  CASE WHEN Status = 'A' THEN 'Active' ELSE 'Inactive' END AS State"}</div>
                        <div className="text-amber-300">FROM Orders;</div>
                      </div>
                    </div>
                  </div>
                </RevealOnScroll>
              </div>

              {/* Step 5 */}
              <div className="relative group">
                <div className="absolute -left-[41px] sm:-left-[73px] w-8 h-8 rounded-full bg-[#050506] border-2 border-rose-400 flex items-center justify-center shadow-[0_0_15px_rgba(244,63,94,0.3)] group-hover:scale-110 transition-transform duration-300">
                  <Cpu size={14} className="text-rose-400" />
                </div>
                
                <RevealOnScroll delay={0}>
                  <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] hover:border-rose-500/10 hover:border-white/10 transition-all duration-500 shadow-xl">
                    <span className="text-xs font-bold text-rose-400 tracking-[0.2em] uppercase">Step 5 • Layer 5</span>
                    <h3 className="text-2xl font-bold text-white mt-2 mb-4 flex items-center gap-3">
                      C# & WPF Generation <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">Active</span>
                    </h3>
                    
                    <p className="text-sm text-gray-400 leading-relaxed font-light mb-6">
                      AI agents combine all intermediate pipeline structures to generate complete enterprise C# backend services and clean XAML files for modern WPF desktop views, strictly adhering to clean MVVM patterns.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-[10px] bg-black/40 p-5 rounded-2xl border border-white/5">
                      <div>
                        <div className="text-gray-500 mb-2 font-sans font-bold">WPF View (OrderView.xaml):</div>
                        <div className="text-rose-400">{'<TextBox Text="{Binding Path=OrderNo}" />'}</div>
                        <div className="text-rose-400">{'<Button Content="Process" Command="{Binding ProcessCmd}" />'}</div>
                      </div>
                      <div className="border-t md:border-t-0 md:border-l border-white/5 pt-3 md:pt-0 md:pl-4">
                        <div className="text-gray-500 mb-2 font-sans font-bold">C# ViewModel (OrderViewModel.cs):</div>
                        <div className="text-rose-300">public ICommand ProcessCmd {"{"} get; {"}"}</div>
                        <div className="text-rose-300">private void ExecuteProcess()</div>
                        <div className="text-rose-300">{"{"}</div>
                        <div className="text-rose-300">    _orderService.ProcessOrder(OrderNo);</div>
                        <div className="text-rose-300">{"}"}</div>
                      </div>
                    </div>
                  </div>
                </RevealOnScroll>
              </div>

            </div>

          </div>
        </section>

        {/* Features & Interactive Playground Section */}
        <section className="py-28 px-6 sm:px-12 border-t border-white/5 relative z-10">
          <div className="max-w-7xl mx-auto flex flex-col lg:flex-row items-center gap-16">
            <div className="w-full lg:w-5/12">
              <RevealOnScroll>
                <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">Why vba_brain?</h2>
                <p className="text-gray-400 text-lg font-light mb-8 leading-relaxed">
                  Manually migrating Access databases takes months of tedious refactoring. vba_brain reduces it to minutes by automating structural AST parsing, relational query optimization, and UI generation.
                </p>
                <ul className="space-y-4 mb-8">
                  {['Automated AST parsing of legacy VBA', 'AI-assisted Contextual Translation', 'Guaranteed SQL Syntax correctness', 'One-click WPF C# scaffold generation'].map((ft, i) => (
                    <li key={i} className="flex items-center gap-3 text-gray-300 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>{ft}</span>
                    </li>
                  ))}
                </ul>
                <div className="p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 flex items-start gap-3">
                  <Terminal size={18} className="text-indigo-400 mt-1 shrink-0" />
                  <p className="text-xs text-gray-400 leading-relaxed">
                    <strong className="text-gray-200">Interactive Demo:</strong> Trigger the AI playground to the right to see how our AST compiler translates a VBA database function to modern async C# Code!
                  </p>
                </div>
              </RevealOnScroll>
            </div>
            
            {/* VS-Code Style Interactive Playground */}
            <div className="lg:w-7/12 w-full">
              <RevealOnScroll delay={150}>
                <div className="rounded-2xl border border-white/10 bg-[#0c0d12] shadow-2xl overflow-hidden relative">
                  
                  {/* Editor Header Bar */}
                  <div className="flex items-center justify-between px-4 py-3 bg-[#11131c] border-b border-white/5 select-none">
                    <div className="flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                      <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                      <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                      <span className="text-xs text-gray-500 font-mono ml-4">vba_brain AI Translator</span>
                    </div>
                    {isConverted && (
                      <button onClick={handleResetConversion} className="text-[10px] text-gray-400 hover:text-white bg-white/5 border border-white/10 px-2 py-0.5 rounded transition-all">
                        Reset Demo
                      </button>
                    )}
                  </div>

                  {/* Editors Side-by-Side */}
                  <div className="grid grid-cols-1 md:grid-cols-2 min-h-[260px] relative">
                    
                    {/* Left Panel: VBA Code */}
                    <div className="p-5 border-r border-white/5 flex flex-col font-mono text-[11px] leading-relaxed relative bg-[#0d0e15]/80">
                      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3 select-none">Access VBA Source</div>
                      <pre className="text-cyan-400 overflow-x-auto whitespace-pre">{vbaCode}</pre>
                    </div>

                    {/* Right Panel: C# Target Code */}
                    <div className="p-5 flex flex-col font-mono text-[11px] leading-relaxed relative bg-[#090a0f]">
                      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3 select-none">Modern C# & EF Core</div>
                      
                      {/* Scan Radar overlay during conversion */}
                      {isConverting && (
                        <div className="absolute inset-0 z-10 radar-scan pointer-events-none" />
                      )}

                      {!isConverting && !isConverted ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center text-gray-500 py-10 select-none">
                          <Cpu size={24} className="mb-2 opacity-30 animate-pulse" />
                          <span>Awaiting Translation Run</span>
                        </div>
                      ) : isConverting ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center text-indigo-400 py-10 select-none">
                          <RefreshCw size={24} className="animate-spin mb-2" />
                          <span className="text-[10px] tracking-wider uppercase font-bold text-indigo-300">{statusText}</span>
                          <span className="text-xs font-bold mt-1 text-gray-300">{progress}%</span>
                        </div>
                      ) : (
                        <pre className="text-purple-300 overflow-x-auto whitespace-pre animate-[fadeIn_0.5s_ease-out]">{csharpCode}</pre>
                      )}
                    </div>
                  </div>

                  {/* Controller Action Overlay */}
                  {!isConverting && !isConverted && (
                    <div className="absolute inset-0 bg-[#0c0d12]/60 backdrop-blur-[2px] flex items-center justify-center z-20">
                      <button
                        onClick={handleStartConversion}
                        className="group flex items-center gap-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-bold text-xs py-3.5 px-7 rounded-xl shadow-[0_4px_25px_rgba(99,102,241,0.4)] hover:shadow-[0_4px_35px_rgba(99,102,241,0.6)] transition-all duration-300 hover:scale-105 active:scale-95"
                      >
                        <Play size={13} className="text-white fill-white" />
                        <span>⚡ Run AI Translation Engine</span>
                      </button>
                    </div>
                  )}
                  
                </div>
              </RevealOnScroll>
            </div>
          </div>
        </section>

        </main>

        {/* Footer */}
        <Footer />

      </div>
    </div>
  );
}
