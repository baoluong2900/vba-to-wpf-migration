"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  ArrowRight, DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Sparkles, ChevronRight, CheckCircle2, RefreshCw, Play,
  Code2, ArrowRightLeft, ShieldCheck, Zap, Layers, Network, 
  Terminal, DatabaseIcon, Workflow, FileCode
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";

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
  const [isMounted, setIsMounted] = useState(false);
  const [activeLayerTab, setActiveLayerTab] = useState(0);

  // Playground states
  const [isConverting, setIsConverting] = useState(false);
  const [isConverted, setIsConverted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Idle");

  useEffect(() => {
    setIsMounted(true);
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

  const layersInfo = [
    {
      id: 0,
      layer: "Layer 1",
      title: "Source Extraction",
      shortDesc: "Deep parses legacy Access databases into structured AST representations.",
      icon: DatabaseZap,
      link: "/layer1",
      color: "cyan",
      badgeColor: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
      glowColor: "rgba(34, 211, 238, 0.18)",
      details: "The system scans the source Access database file (.accdb or .mdb). The AI Engine performs a deep structural analysis of schemas (Tables, Relations), UI definitions (Forms, Reports), and legacy VBA macros, translating them into a unified AST JSON format.",
      inputLabel: "Legacy Access Input:",
      inputContent: "📄 MS Access File\n  ├─ Tables: tblOrders\n  ├─ UI Form: F_OrderEntry\n  └─ VBA: Form_F_OrderEntry.cls",
      outputLabel: "Structured AST Output:",
      outputContent: '{\n  "type": "Form",\n  "name": "F_OrderEntry",\n  "controls": [\n    { \n      "type": "TextBox", \n      "name": "txtOrderId" \n    }\n  ]\n}'
    },
    {
      id: 1,
      layer: "Layer 2",
      title: "Logic Analysis",
      shortDesc: "AI engine maps complex entity relationships to extract core business logic.",
      icon: Bot,
      link: "/layer2",
      color: "purple",
      badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/20",
      glowColor: "rgba(168, 85, 247, 0.18)",
      details: "AI Agents automatically parse the AST syntax tree to map complex data flow relationships (Dependency Graph). This isolates embedded legacy business logic from VBA modules, identifying how UI Forms interact with queries and tables.",
      inputLabel: "AST Elements:",
      inputContent: "• Form_Open event trigger\n• Command click handlers\n• VBA Recordset query dependencies",
      outputLabel: "Logic Graph Output:",
      outputContent: 'Form: F_OrderEntry\n  └─ triggers ClickEvent\n      └─ calls Q_GetOrder\n          └─ reads tblOrders (Col: CustName)'
    },
    {
      id: 2,
      layer: "Layer 3",
      title: "Excel Documentation",
      shortDesc: "Auto-translates logic into technical Excel specifications for review.",
      icon: FileSpreadsheet,
      link: "/layer3",
      color: "emerald",
      badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      glowColor: "rgba(52, 211, 153, 0.18)",
      details: "Converts database schemas and extracted logic rules into standardized Excel technical specification sheets. This allows engineers to manually inspect, trace, and approve logical mappings before compiling to C#/.NET.",
      inputLabel: "Logic Mapping Trees:",
      inputContent: "• Screen Form specifications\n• Database layout relations\n• Logic rule extraction arrays",
      outputLabel: "Excel Specification Sheets:",
      outputContent: "📊 BD_Specification.xlsx (12 Tables)\n📊 DD_ScreenDefinition.xlsx (8 Forms)\n📊 DD_MacroModule.xlsx (35 Macros)"
    },
    {
      id: 3,
      layer: "Layer 4",
      title: "SQL Dialect Conversion",
      shortDesc: "Safely converts Access SQL dialects into optimized Oracle/SQL Server scripts.",
      icon: Database,
      link: "/layer4",
      color: "amber",
      badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/20",
      glowColor: "rgba(251, 191, 36, 0.18)",
      details: "Translates proprietary MS Access SQL functions (e.g. IIf, Nz, InStr) into optimized database dialects like Oracle SQL, PostgreSQL, or SQL Server. The conversion agent supports direct schema validation and syntax checks.",
      inputLabel: "Access SQL Dialect:",
      inputContent: "SELECT OrderID, \n  IIf(Status='A', \n      'Active', 'Inactive') AS State\nFROM Orders;",
      outputLabel: "Target Dialect (Oracle SQL):",
      outputContent: "SELECT OrderID,\n  CASE WHEN Status = 'A' \n       THEN 'Active'\n       ELSE 'Inactive' \n  END AS State\nFROM Orders;"
    },
    {
      id: 4,
      layer: "Layer 5",
      title: "C# & WPF Generation",
      shortDesc: "Synthesizes modern WPF UI components and C# logic to finalize migration.",
      icon: Cpu,
      link: "/layer5",
      color: "rose",
      badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/20",
      glowColor: "rgba(244, 63, 94, 0.18)",
      details: "AI agents combine all intermediate pipeline structures to generate complete enterprise C# backend services and clean XAML files for modern WPF desktop views, strictly adhering to clean MVVM patterns.",
      inputLabel: "WPF UI XAML Layout:",
      inputContent: '<TextBox Text="{Binding OrderNo}" />\n<Button Content="Process"\n  Command="{Binding ProcessCmd}" />',
      outputLabel: "C# ViewModel CodeBehind:",
      outputContent: "public ICommand ProcessCmd { get; }\nprivate void ExecuteProcess()\n{\n    _orderService.Process(OrderNo);\n}"
    }
  ];

  return (
    <div className="flex-1 w-full min-h-screen bg-[#030303] text-gray-200 font-sans selection:bg-indigo-500/30 selection:text-white relative overflow-x-hidden scroll-smooth">
      <style>{`
        /* Premium entrance slide up animation */
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(35px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        /* Floating animations for background components */
        @keyframes floatingBadges {
          0% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(-15px) rotate(3deg); }
          100% { transform: translateY(0px) rotate(0deg); }
        }

        @keyframes floatingSlow {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -30px) scale(1.05); }
          66% { transform: translate(-20px, 20px) scale(0.95); }
          100% { transform: translate(0px, 0px) scale(1); }
        }

        /* Pulsing neon outline */
        @keyframes neonPulse {
          0%, 100% { box-shadow: 0 0 15px rgba(99, 102, 241, 0.15), inset 0 1px 1px rgba(255,255,255,0.02); }
          50% { box-shadow: 0 0 30px rgba(99, 102, 241, 0.35), inset 0 1px 1px rgba(255,255,255,0.05); }
        }

        @keyframes scanVertical {
          0% { background-position: 0 -200px; }
          100% { background-position: 0 400px; }
        }

        .animate-fade-in-up {
          opacity: 0;
          animation: fadeInUp 0.9s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .animate-glow-1 {
          animation: floatingSlow 15s ease-in-out infinite;
        }
        .animate-glow-2 {
          animation: floatingSlow 18s ease-in-out infinite alternate;
        }

        .grid-mesh {
          background-image: radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.015) 1px, transparent 0);
          background-size: 24px 24px;
        }
        
        .premium-border-beam {
          position: relative;
        }
        .premium-border-beam::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          padding: 1px;
          background: linear-gradient(to bottom right, rgba(99, 102, 241, 0.4), transparent, rgba(168, 85, 247, 0.4));
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        .shimmer-rainbow-text {
          background-image: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6, #60a5fa);
          background-size: 200% auto;
          -webkit-background-clip: text;
          background-clip: text;
          animation: shine 8s linear infinite;
        }
        @keyframes shine {
          to { background-position: 200% center; }
        }

        .radar-scan-line {
          background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.2) 50%, transparent 100%);
          background-size: 100% 200px;
          animation: scanVertical 2.5s linear infinite;
        }
      `}</style>

      {/* Futuristic Glow Backdrops */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[5%] left-[10%] w-[500px] h-[500px] rounded-full bg-indigo-500/10 blur-[150px] animate-glow-1"></div>
        <div className="absolute bottom-[20%] right-[5%] w-[600px] h-[600px] rounded-full bg-purple-500/10 blur-[180px] animate-glow-2"></div>
        <div className="absolute inset-0 grid-mesh opacity-80"></div>

        {/* Floating tech background symbols */}
        <div className="absolute top-[18%] right-[15%] opacity-20 text-neutral-600 animate-[floatingBadges_7s_ease-in-out_infinite] hidden lg:block">
          <DatabaseIcon size={64} className="text-cyan-500/30" />
        </div>
        <div className="absolute top-[55%] left-[8%] opacity-20 text-neutral-600 animate-[floatingBadges_9s_ease-in-out_infinite_2s] hidden lg:block">
          <Workflow size={72} className="text-purple-500/30" />
        </div>
        <div className="absolute bottom-[25%] left-[45%] opacity-15 text-neutral-600 animate-[floatingBadges_8s_ease-in-out_infinite_1s] hidden lg:block">
          <FileCode size={56} className="text-rose-500/30" />
        </div>
      </div>

      <div className="relative z-10 flex flex-col w-full min-h-screen">
        {/* Navbar */}
        <Header />

        <main className="flex-1 w-full flex flex-col">
          
          {/* 1. Hero & Value Proposition Section (Deluxe spacing + Entrance Animations) */}
          <section className="w-full pt-40 pb-32 px-6 md:px-12 flex justify-center border-b border-neutral-900/80 relative">
            <div className="max-w-6xl w-full flex flex-col items-center text-center">
              
              {/* Sparkles Tech Tag */}
              <div className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full bg-neutral-950/80 border border-neutral-800 text-indigo-300 text-xs font-semibold tracking-wide mb-10 animate-fade-in-up"
                style={{ animationDelay: "100ms" }}>
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                <span>Next-Gen VBA to C# Scaffold Migration</span>
              </div>
              
              {/* Premium Heading */}
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white mb-10 leading-[1.12] animate-fade-in-up"
                style={{ animationDelay: "250ms" }}>
                Rebuild Legacy Access <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 shimmer-rainbow-text">
                  in 5 Intelligent Layers
                </span>
              </h1>
              
              {/* Subtitle */}
              <p className="text-base sm:text-lg lg:text-xl text-neutral-400 max-w-3xl mx-auto mb-16 font-light leading-relaxed animate-fade-in-up"
                style={{ animationDelay: "400ms" }}>
                An advanced multi-agent AI pipeline that extracts legacy Access database structures and business logic rules, generating modern WPF client architectures with absolute compile-safe accuracy.
              </p>
              
              {/* Action Buttons */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mb-28 w-full max-w-md mx-auto animate-fade-in-up"
                style={{ animationDelay: "550ms" }}>
                <Link href="/layer1" className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 bg-white text-black font-semibold py-4.5 px-9 rounded-full shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:scale-[1.04] hover:-translate-y-0.5 transition-all duration-300">
                  <span>Start Live Migration</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link href="#timeline-tabs" className="w-full sm:w-auto inline-flex items-center justify-center bg-neutral-950 text-neutral-300 hover:text-white font-semibold py-4.5 px-9 rounded-full border border-neutral-800 hover:border-neutral-700 transition-all duration-300">
                  Explore Architecture
                </Link>
              </div>

              {/* Core Metrics (Spacious gap-8 + entrance animations) */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 w-full mt-10 animate-fade-in-up"
                style={{ animationDelay: "700ms" }}>
                {[
                  { icon: Zap, value: "10x Faster", label: "Workflow Delivery", desc: "Reduces legacy manual rewrites from months to days." },
                  { icon: ShieldCheck, value: "99.8% Accuracy", label: "AST Structure Parsing", desc: "Verifies relational schemas, macros, and modules." },
                  { icon: Network, value: "Clean MVVM", label: "WPF C# Code Generation", desc: "Compiles clean, native C# templates automatically." }
                ].map((item, idx) => {
                  const Icon = item.icon;
                  return (
                    <div key={idx} className="bg-neutral-950/40 backdrop-blur-md border border-neutral-900 rounded-3xl p-8 text-left premium-border-beam relative hover:scale-[1.03] hover:-translate-y-1 transition-all duration-500 shadow-xl"
                      style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}>
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-6 transition-all duration-300 group-hover:scale-110">
                        <Icon className="w-5 h-5 text-indigo-400" />
                      </div>
                      <div className="text-xl font-bold text-white mb-1.5">{item.value}</div>
                      <div className="text-xs font-semibold text-neutral-400 tracking-wide mb-3">{item.label}</div>
                      <p className="text-xs text-neutral-500 leading-relaxed font-light">{item.desc}</p>
                    </div>
                  );
                })}
              </div>

            </div>
          </section>

          {/* 2. Interactive Translation Playground */}
          <section className="w-full py-32 px-6 md:px-12 flex justify-center border-b border-neutral-900/80 bg-[#050506]/85 relative">
            <div className="max-w-6xl w-full grid grid-cols-1 lg:grid-cols-12 gap-16 items-center">
              
              {/* Left Column: Text & Features */}
              <div className="lg:col-span-5 flex flex-col gap-8">
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Interactive Playground</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight leading-tight">
                  Watch legacy VBA evolve into C# in real time
                </h2>
                <p className="text-neutral-400 font-light leading-relaxed text-sm">
                  Legacy Access databases embed logic directly inside forms and queries. vba_brain parses the entire AST representation, compiles logic trees, and outputs modern async/await C# architecture automatically.
                </p>
                <div className="flex flex-col gap-4 font-sans text-sm text-neutral-300 mt-2">
                  <div className="flex items-center gap-3 hover:translate-x-1 transition-transform duration-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Converts Access VBA syntax directly to async C#</span>
                  </div>
                  <div className="flex items-center gap-3 hover:translate-x-1 transition-transform duration-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Scaffolds modern EF Core models from tables</span>
                  </div>
                  <div className="flex items-center gap-3 hover:translate-x-1 transition-transform duration-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Validates compile success via compiler agents</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Code Editor View */}
              <div className="lg:col-span-7 w-full flex justify-center">
                <div className="w-full max-w-2xl bg-[#090a0f] border border-neutral-800 rounded-3xl overflow-hidden shadow-2xl relative"
                  style={{ animation: "neonPulse 5s ease-in-out infinite" }}>
                  
                  {/* Editor Top Bar */}
                  <div className="flex items-center justify-between px-6 py-5 bg-[#0d0e15] border-b border-neutral-900 select-none">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                      <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                      <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                      <span className="text-[11px] font-mono text-neutral-500 ml-3">vba_brain_compiler_agent.py</span>
                    </div>
                    {isConverted && (
                      <button onClick={handleResetConversion} className="text-[10px] text-neutral-400 hover:text-white bg-neutral-900 border border-neutral-800 px-3.5 py-1.5 rounded-full transition-all cursor-pointer">
                        Reset Demo
                      </button>
                    )}
                  </div>

                  {/* Code Panel Split */}
                  <div className="grid grid-cols-1 md:grid-cols-2 relative font-mono text-[11px] leading-relaxed">
                    
                    {/* Left: Source VBA */}
                    <div className="p-8 bg-[#0d0e15]/40 flex flex-col border-b md:border-b-0 md:border-r border-neutral-900">
                      <div className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest mb-4">VBA Source</div>
                      <pre className="text-cyan-400/90 whitespace-pre overflow-x-auto">{vbaCode}</pre>
                    </div>

                    {/* Right: Output C# */}
                    <div className="p-8 bg-[#06070a] flex flex-col relative min-h-[240px]">
                      <div className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest mb-4">C# Target (EF Core)</div>
                      
                      {isConverting && (
                        <div className="absolute inset-0 z-10 radar-scan-line pointer-events-none" />
                      )}

                      {!isConverting && !isConverted ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center text-neutral-600 py-12 select-none">
                          <Cpu className="w-6 h-6 mb-3 opacity-30 animate-pulse text-indigo-400" />
                          <span>Awaiting compiler execution...</span>
                        </div>
                      ) : isConverting ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center text-indigo-400 py-12 select-none">
                          <RefreshCw className="w-6 h-6 animate-spin mb-3 text-indigo-400" />
                          <span className="text-[9px] tracking-wider uppercase font-bold text-neutral-400">{statusText}</span>
                          <span className="text-sm font-bold mt-1 text-white">{progress}%</span>
                        </div>
                      ) : (
                        <pre className="text-purple-300/90 whitespace-pre overflow-x-auto animate-[fadeIn_0.5s_ease-out]">{csharpCode}</pre>
                      )}
                    </div>
                  </div>

                  {/* Compilation Play Trigger */}
                  {!isConverting && !isConverted && (
                    <div className="absolute inset-0 bg-neutral-950/60 backdrop-blur-[1.5px] flex items-center justify-center z-25">
                      <button
                        onClick={handleStartConversion}
                        className="group flex items-center gap-2.5 bg-white text-black font-semibold text-xs py-4 px-8 rounded-full shadow-2xl hover:scale-105 active:scale-95 transition-all duration-300 cursor-pointer"
                      >
                        <Play className="w-3.5 h-3.5 text-black fill-black" />
                        <span>Execute Compiler Agent</span>
                      </button>
                    </div>
                  )}

                </div>
              </div>

            </div>
          </section>

          {/* 3. Interactive 5-Layer Workspace Tabs */}
          <section id="timeline-tabs" className="w-full py-32 px-6 md:px-12 flex justify-center relative border-b border-neutral-900/80">
            <div className="max-w-6xl w-full flex flex-col items-center">
              
              {/* Header */}
              <div className="text-center mb-20 max-w-2xl">
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase mb-3">
                  <Layers className="w-4 h-4" />
                  <span>Pipeline Architecture</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">Interactive 5-Layer Workflow</h2>
                <p className="text-neutral-400 text-sm font-light leading-relaxed">
                  Select a layer below to inspect how legacy components are parsed, verified, and mapped before final C# code generation.
                </p>
              </div>

              {/* Tab Switcher Grid */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 w-full max-w-5xl mb-16 relative">
                {layersInfo.map((l, idx) => {
                  const Icon = l.icon;
                  const isActive = activeLayerTab === idx;
                  return (
                    <button
                      key={idx}
                      onClick={() => setActiveLayerTab(idx)}
                      className={`flex flex-col items-center gap-3 p-5 rounded-2xl border transition-all duration-500 cursor-pointer relative overflow-hidden group ${
                        isActive 
                          ? "bg-neutral-900/60 border-indigo-500/50 shadow-[0_0_25px_rgba(99,102,241,0.2)] text-white scale-[1.02]" 
                          : "bg-neutral-950/20 border-neutral-900 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-950/40 hover:scale-[1.01]"
                      }`}
                    >
                      {/* Active floating neon indicator */}
                      {isActive && (
                        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-400 via-indigo-500 to-purple-500 animate-[gradientMove_3s_linear_infinite]" />
                      )}
                      
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-300 ${
                        isActive ? "bg-indigo-500/10 text-indigo-400 scale-110" : "bg-neutral-900 text-neutral-500 group-hover:text-neutral-300"
                      }`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex flex-col items-center">
                        <span className="text-[9px] font-bold tracking-wider uppercase opacity-60">{l.layer}</span>
                        <span className="text-xs font-bold whitespace-nowrap mt-0.5">{l.title}</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Tab Content Box (Deluxe padding) */}
              <div className="w-full bg-[#050506] border border-neutral-800 rounded-3xl p-8 md:p-12 shadow-2xl relative overflow-hidden transition-all duration-500">
                {/* Glow Ring Effect */}
                <div 
                  className="absolute -top-1/2 -left-1/2 w-full h-full rounded-full blur-[140px] pointer-events-none transition-all duration-700"
                  style={{ background: layersInfo[activeLayerTab].glowColor }}
                />

                <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
                  
                  {/* Text Details (Left 5 cols) */}
                  <div className="lg:col-span-5 flex flex-col gap-6">
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border w-fit ${layersInfo[activeLayerTab].badgeColor}`}>
                      <Sparkles className="w-3 h-3" />
                      {layersInfo[activeLayerTab].layer} Active
                    </span>
                    <h3 className="text-2xl font-bold text-white leading-snug">{layersInfo[activeLayerTab].title}</h3>
                    <p className="text-neutral-400 text-sm leading-relaxed font-light">
                      {layersInfo[activeLayerTab].details}
                    </p>
                    <Link 
                      href={layersInfo[activeLayerTab].link} 
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 mt-4 group"
                    >
                      <span>Open {layersInfo[activeLayerTab].layer} Workspace</span>
                      <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform duration-300" />
                    </Link>
                  </div>

                  {/* Terminal Demos (Right 7 cols, spacious p-8 with gaps) */}
                  <div className="lg:col-span-7 w-full grid grid-cols-1 md:grid-cols-2 gap-8 font-mono text-[10px] bg-black/40 p-8 rounded-2xl border border-neutral-900">
                    
                    {/* Input */}
                    <div className="flex flex-col gap-2">
                      <div className="text-neutral-500 font-bold select-none">{layersInfo[activeLayerTab].inputLabel}</div>
                      <pre className="text-neutral-400/90 whitespace-pre overflow-x-auto leading-relaxed bg-[#0d0e15]/20 p-4 rounded-xl border border-neutral-900/60 transition-all duration-300 hover:border-neutral-800">{layersInfo[activeLayerTab].inputContent}</pre>
                    </div>

                    {/* Output */}
                    <div className="border-t md:border-t-0 md:border-l border-neutral-900 pt-6 md:pt-0 md:pl-8 flex flex-col gap-2">
                      <div className="text-neutral-500 font-bold select-none">{layersInfo[activeLayerTab].outputLabel}</div>
                      <pre className="text-indigo-300/95 whitespace-pre overflow-x-auto leading-relaxed bg-[#0d0e15]/20 p-4 rounded-xl border border-neutral-900/60 transition-all duration-300 hover:border-neutral-800">{layersInfo[activeLayerTab].outputContent}</pre>
                    </div>

                  </div>

                </div>
              </div>

            </div>
          </section>

          {/* 4. Technology Stack & Rules Section */}
          <section className="w-full py-32 px-6 md:px-12 flex justify-center bg-[#050506]/85 border-b border-neutral-900/80">
            <div className="max-w-6xl w-full flex flex-col items-center">
              
              <div className="text-center mb-20 max-w-2xl">
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase mb-3">
                  <Code2 className="w-4 h-4" />
                  <span>Scaffold Architecture</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">Designed for Clean Code Standards</h2>
                <p className="text-neutral-400 text-sm font-light leading-relaxed">
                  Generated code is built to last. Our parser outputs strictly clean, modular, and testable code adhering to industry standards.
                </p>
              </div>

              {/* Rules Grid (Spacious p-8, responsive hover transitions) */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full">
                {[
                  { title: "Domain Driven Design (DDD)", desc: "WPF C# code is split cleanly into Domain, Application, Infrastructure, and UI projects to ensure modern enterprise architecture standards." },
                  { title: "Clean MVVM Separation", desc: "No hardcoded event handlers in WPF window files. Standardized ViewModel commands bind directly to reactive properties cleanly." },
                  { title: "Secure Config Files", desc: "All sensitive API keys, local ports, database credentials, and environments are ignored recursively, avoiding raw commits." }
                ].map((item, idx) => (
                  <div key={idx} className="bg-neutral-950/50 border border-neutral-900 rounded-3xl p-8 flex flex-col hover:border-neutral-800 hover:-translate-y-1 hover:shadow-2xl hover:bg-neutral-900/10 transition-all duration-500"
                    style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}>
                    <div className="text-sm font-bold text-white mb-4">{item.title}</div>
                    <p className="text-xs sm:text-sm text-neutral-400 font-light leading-relaxed">{item.desc}</p>
                  </div>
                ))}
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
