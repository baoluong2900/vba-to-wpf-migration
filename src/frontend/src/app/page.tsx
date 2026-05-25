"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { motion, AnimatePresence, useScroll, useSpring } from "framer-motion";
import { 
  ArrowRight, DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Sparkles, ChevronRight, CheckCircle2, RefreshCw, Play,
  Code2, ArrowRightLeft, ShieldCheck, Zap, Layers, Network, 
  Terminal, DatabaseIcon, Workflow, FileCode, ArrowUpRight, 
  Monitor, Settings, HardDrive, Check, PlayCircle, Eye, RefreshCcw
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

  // Terminal logger states
  const [logLines, setLogLines] = useState<string[]>([
    "System initialized. gRPC migration listener active on port 50051.",
    "Database connection factory initialized: MongoDB local state active."
  ]);

  // Page Scroll Progress
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  useEffect(() => {
    setIsMounted(true);

    // Live terminal logger effect
    const logs = [
      "[Layer 1] Extracted AST JSON for F_Menu.frm (12 controls parsed).",
      "[Layer 2] Mapping logic graph: Form F_Menu ──► Query Q_ActiveProducts.",
      "[Layer 4] Converting Access SQL 'IIf(Stock <= 0, 0, Stock)' to Oracle SQL.",
      "[Layer 5] Generating Avalonia WPF View Model: F_MenuViewModel.cs",
      "[Layer 5] Compile validation: compile successful (0 errors, 2 warnings).",
      "[Layer 3] Seeded Excel specification workbook: DD_ScreenDefinition.xlsx",
      "[Layer 1] Parsed VBA Module Mod_CommonUtils: 14 functions mapped."
    ];

    let logIdx = 0;
    const interval = setInterval(() => {
      setLogLines(prev => {
        const next = [...prev, `[${new Date().toLocaleTimeString("vi-VN")}] ${logs[logIdx]}`];
        if (next.length > 8) next.shift(); // Keep logs clean
        return next;
      });
      logIdx = (logIdx + 1) % logs.length;
    }, 4000);

    return () => clearInterval(interval);
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
      glowColor: "rgba(34, 211, 238, 0.15)",
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
      glowColor: "rgba(168, 85, 247, 0.15)",
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
      glowColor: "rgba(52, 211, 153, 0.15)",
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
      glowColor: "rgba(251, 191, 36, 0.15)",
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
      glowColor: "rgba(244, 63, 94, 0.15)",
      details: "AI agents combine all intermediate pipeline structures to generate complete enterprise C# backend services and clean XAML files for modern WPF desktop views, strictly adhering to clean MVVM patterns.",
      inputLabel: "WPF UI XAML Layout:",
      inputContent: '<TextBox Text="{Binding OrderNo}" />\n<Button Content="Process"\n  Command="{Binding ProcessCmd}" />',
      outputLabel: "C# ViewModel CodeBehind:",
      outputContent: "public ICommand ProcessCmd { get; }\nprivate void ExecuteProcess()\n{\n    _orderService.Process(OrderNo);\n}"
    }
  ];

  // Animation configuration constants
  const fadeInUpVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { 
      opacity: 1, 
      y: 0,
      transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] as const }
    }
  };

  const staggerContainerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15,
        delayChildren: 0.1
      }
    }
  };

  return (
    <div className="flex-1 w-full min-h-screen bg-[#030303] text-gray-200 font-sans selection:bg-indigo-500/30 selection:text-white relative overflow-x-hidden scroll-smooth">
      
      {/* 1. Scroll Progress Bar */}
      <motion.div 
        className="fixed top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 origin-left z-50" 
        style={{ scaleX }} 
      />

      <style>{`
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

        .animate-laser {
          position: absolute;
          width: 60px;
          height: 2px;
          background: linear-gradient(90deg, transparent, #818cf8, #a78bfa, transparent);
          animation: laserTravel 4s linear infinite;
        }

        .animate-marquee-left {
          display: flex;
          width: max-content;
          animation: marqueeScroll 30s linear infinite;
        }

        @keyframes scanVertical {
          0% { background-position: 0 -200px; }
          100% { background-position: 0 400px; }
        }

        @keyframes laserTravel {
          0% { left: 0%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { left: 100%; opacity: 0; }
        }

        @keyframes marqueeScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>

      {/* Futuristic Glow Backdrops */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <motion.div 
          animate={{
            y: [0, -30, 0],
            x: [0, 20, 0],
            scale: [1, 1.05, 1]
          }}
          transition={{
            duration: 18,
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className="absolute top-[5%] left-[10%] w-[300px] sm:w-[500px] h-[300px] sm:h-[500px] rounded-full bg-indigo-500/10 blur-[120px] sm:blur-[160px]"
        />
        <motion.div 
          animate={{
            y: [0, 30, 0],
            x: [0, -25, 0],
            scale: [1, 0.95, 1]
          }}
          transition={{
            duration: 22,
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className="absolute bottom-[20%] right-[5%] w-[350px] sm:w-[600px] h-[350px] sm:h-[600px] rounded-full bg-purple-500/10 blur-[130px] sm:blur-[190px]"
        />
        <div className="absolute inset-0 grid-mesh opacity-80" />

        {/* Floating tech background elements */}
        <motion.div 
          animate={{ y: [0, -12, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[18%] right-[12%] opacity-15 text-neutral-600 hidden lg:block"
        >
          <DatabaseIcon size={64} className="text-cyan-500/30" />
        </motion.div>
        <motion.div 
          animate={{ y: [0, 15, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute top-[55%] left-[6%] opacity-15 text-neutral-600 hidden lg:block"
        >
          <Workflow size={72} className="text-purple-500/30" />
        </motion.div>
        <motion.div 
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="absolute bottom-[25%] left-[45%] opacity-12 text-neutral-600 hidden lg:block"
        >
          <FileCode size={56} className="text-rose-500/30" />
        </motion.div>
      </div>

      <div className="relative z-10 flex flex-col w-full min-h-screen">
        {/* Navbar */}
        <Header />

        <main className="flex-1 w-full flex flex-col">
          
          {/* 1. Hero & Value Proposition Section */}
          <section className="w-full pt-36 sm:pt-48 md:pt-60 pb-24 sm:pb-36 px-6 sm:px-12 md:px-16 flex justify-center border-b border-neutral-900/80 relative">
            <motion.div 
              initial="hidden"
              animate="visible"
              variants={staggerContainerVariants}
              className="max-w-6xl w-full flex flex-col items-center text-center"
            >
              {/* Sparkles Tech Tag */}
              <motion.div 
                variants={fadeInUpVariants}
                className="inline-flex items-center gap-2.5 px-4.5 py-2.5 rounded-full bg-neutral-950/80 border border-neutral-800 text-indigo-300 text-xs font-semibold tracking-wider mb-8"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
                <span>Next-Gen VBA to C# Scaffold Migration</span>
              </motion.div>
              
              {/* Premium Heading */}
              <motion.h1 
                variants={fadeInUpVariants}
                className="text-4xl sm:text-6xl md:text-7xl lg:text-8xl font-extrabold tracking-tight text-white mb-8 leading-[1.15]"
              >
                Rebuild Legacy Access <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 shimmer-rainbow-text">
                  in 5 Intelligent Layers
                </span>
              </motion.h1>
              
              {/* Subtitle */}
              <motion.p 
                variants={fadeInUpVariants}
                className="text-sm sm:text-lg md:text-xl lg:text-2xl text-neutral-400 max-w-3xl mx-auto mb-16 font-light leading-relaxed tracking-wide"
              >
                An advanced multi-agent AI pipeline that extracts legacy Access database structures and business logic rules, generating modern WPF client architectures with absolute compile-safe accuracy.
              </motion.p>
              
              {/* Action Buttons */}
              <motion.div 
                variants={fadeInUpVariants}
                className="flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-8 mb-28 w-full max-w-2xl mx-auto"
              >
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }} className="w-full sm:w-auto">
                  <Link href="/layer1" className="w-full sm:w-auto inline-flex items-center justify-center gap-3.5 bg-gradient-to-r from-indigo-500 via-purple-600 to-pink-500 text-white font-extrabold py-5 px-14 text-sm sm:text-base tracking-[0.2em] uppercase rounded-full shadow-[0_0_35px_rgba(168,85,247,0.35)] hover:shadow-[0_0_55px_rgba(168,85,247,0.6)] transition-all duration-300">
                    <span>Start Live Migration</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </motion.div>
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }} className="w-full sm:w-auto">
                  <Link href="#timeline-tabs" className="w-full sm:w-auto inline-flex items-center justify-center bg-white/5 backdrop-blur-md text-white font-extrabold py-5 px-14 text-sm sm:text-base tracking-[0.2em] uppercase rounded-full border border-white/10 hover:border-white/20 hover:bg-white/10 shadow-[0_4px_30px_rgba(0,0,0,0.3)] transition-all duration-300">
                    Explore Architecture
                  </Link>
                </motion.div>
              </motion.div>

              {/* Live Transformation Bridge Layout */}
              <motion.div 
                variants={fadeInUpVariants}
                className="w-full max-w-5xl bg-neutral-950/40 backdrop-blur-md border border-neutral-900 rounded-[32px] p-8 sm:p-14 md:p-20 relative overflow-hidden mb-8"
              >
                {/* Connecting Laser Line */}
                <div className="absolute top-1/2 left-[22%] right-[22%] h-[1px] bg-neutral-800/80 -translate-y-1/2 hidden md:block">
                  <div className="animate-laser top-[-1px] left-0"></div>
                </div>

                <div className="flex flex-col md:flex-row items-center justify-between gap-12 md:gap-16 relative z-10">
                  
                  {/* Left Side: Legacy Tech Stack */}
                  <motion.div 
                    whileHover={{ y: -5 }}
                    className="flex flex-col items-center gap-6 bg-neutral-900/30 border border-neutral-855 p-8 sm:p-10 rounded-3xl w-full md:w-80 shadow-lg transition-all duration-300"
                  >
                    <span className="text-xs font-bold text-cyan-400 tracking-[0.25em] uppercase">Legacy Stack</span>
                    <div className="flex items-center gap-4">
                      <div className="w-11 h-11 rounded-xl bg-[#0e2c36] flex items-center justify-center border border-cyan-800/50">
                        <DatabaseZap className="w-5 h-5 text-cyan-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm sm:text-base font-extrabold text-white">Access Database</div>
                        <div className="text-xs text-neutral-500 font-mono mt-0.5">.accdb / .mdb tables</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="w-11 h-11 rounded-xl bg-[#1a0e36] flex items-center justify-center border border-purple-800/50">
                        <FileSpreadsheet className="w-5 h-5 text-purple-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm sm:text-base font-extrabold text-white">VBA Screen Code</div>
                        <div className="text-xs text-neutral-500 font-mono mt-0.5">Macros & Functions</div>
                      </div>
                    </div>
                  </motion.div>

                  {/* Middle Node: AI core converter */}
                  <div className="relative flex flex-col items-center select-none">
                    <motion.div 
                      whileHover={{ scale: 1.05 }}
                      className="w-24 sm:w-28 h-24 sm:h-28 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_40px_rgba(99,102,241,0.4)] animate-pulse cursor-pointer"
                    >
                      <Bot className="w-10 sm:w-12 h-10 sm:h-12 text-white animate-bounce" />
                    </motion.div>
                    <div className="text-xs sm:text-sm font-bold text-white mt-6 tracking-widest uppercase">vba_brain AI Core</div>
                    <div className="text-[10px] text-indigo-400 mt-2 font-mono uppercase">Pipeline Active</div>
                  </div>

                  {/* Right Side: Modern Target */}
                  <motion.div 
                    whileHover={{ y: -5 }}
                    className="flex flex-col items-center gap-6 bg-neutral-900/30 border border-neutral-855 p-8 sm:p-10 rounded-3xl w-full md:w-80 shadow-lg transition-all duration-300"
                  >
                    <span className="text-xs font-bold text-rose-400 tracking-[0.25em] uppercase">Modern Target</span>
                    <div className="flex items-center gap-4">
                      <div className="w-11 h-11 rounded-xl bg-[#2d0e14] flex items-center justify-center border border-rose-800/50">
                        <Cpu className="w-5 h-5 text-rose-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm sm:text-base font-extrabold text-white">Avalonia WPF Client</div>
                        <div className="text-xs text-neutral-500 font-mono mt-0.5">Modern C# & MVVM</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="w-11 h-11 rounded-xl bg-[#2c1d0e] flex items-center justify-center border border-amber-800/50">
                        <Database className="w-5 h-5 text-amber-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm sm:text-base font-extrabold text-white">Oracle SQL Server</div>
                        <div className="text-xs text-neutral-500 font-mono mt-0.5">Optimized Dialect</div>
                      </div>
                    </div>
                  </motion.div>

                </div>
              </motion.div>

            </motion.div>
          </section>

          {/* 2. Interactive Translation Playground */}
          <section className="w-full py-28 sm:py-36 md:py-48 px-6 sm:px-12 md:px-16 flex justify-center border-b border-neutral-900/80 bg-[#050506]/80 relative">
            <div className="max-w-6xl w-full flex flex-col items-center gap-20">
              
              {/* Header Title */}
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="text-center max-w-3xl flex flex-col items-center"
              >
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase mb-5">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Interactive Playground</span>
                </div>
                <h2 className="text-3xl sm:text-5xl md:text-6xl font-extrabold text-white tracking-wide mb-8 leading-[1.25]">
                  Watch legacy VBA evolve into C# in real time
                </h2>
                <p className="text-neutral-300 font-light leading-loose text-sm sm:text-base max-w-3xl">
                  Legacy Access databases embed logic directly inside forms and queries. vba_brain parses the entire AST representation, compiles logic trees, and outputs modern C# EF Core architecture.
                </p>
              </motion.div>

              {/* Code Editor View */}
              <motion.div 
                initial={{ opacity: 0, scale: 0.96 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="w-full max-w-6xl bg-[#090a0f] border border-neutral-850 rounded-[32px] overflow-hidden shadow-2xl relative"
                style={{ animation: "neonPulse 5s ease-in-out infinite" }}
              >
                {/* Editor Top Bar */}
                <div className="flex items-center justify-between px-6 sm:px-8 py-5 sm:py-6 bg-[#0d0e15] border-b border-neutral-900 select-none">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                    <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                    <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                    <span className="text-[11px] font-mono text-neutral-550 ml-3">vba_brain_compiler_agent.py</span>
                  </div>
                  {isConverted && (
                    <motion.button 
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={handleResetConversion} 
                      className="text-xs text-neutral-455 hover:text-white bg-neutral-900 border border-neutral-800 px-4 py-2 rounded-full transition-all cursor-pointer font-semibold"
                    >
                      Reset Demo
                    </motion.button>
                  )}
                </div>

                {/* Code Panel Split */}
                <div className="grid grid-cols-1 md:grid-cols-2 relative font-mono text-xs sm:text-sm leading-relaxed">
                  
                  {/* Left: Source VBA */}
                  <div className="p-8 sm:p-12 bg-[#0d0e15]/45 flex flex-col border-b md:border-b-0 md:border-r border-neutral-900">
                    <div className="text-[10px] font-bold text-neutral-550 uppercase tracking-widest mb-6 font-sans">VBA Source</div>
                    <pre className="text-cyan-400/90 whitespace-pre overflow-x-auto leading-relaxed">{vbaCode}</pre>
                  </div>

                  {/* Right: Output C# */}
                  <div className="p-8 sm:p-12 bg-[#06070a] flex flex-col relative min-h-[300px]">
                    <div className="text-[10px] font-bold text-neutral-550 uppercase tracking-widest mb-6 font-sans">C# Target (EF Core)</div>
                    
                    {isConverting && (
                      <div className="absolute inset-0 z-10 radar-scan-line pointer-events-none" />
                    )}

                    <AnimatePresence mode="wait">
                      {!isConverting && !isConverted && (
                        <motion.div 
                          key="awaiting"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="flex-1 flex flex-col items-center justify-center text-center text-neutral-600 py-16 select-none"
                        >
                          <Cpu className="w-8 h-8 mb-4 opacity-30 animate-pulse text-indigo-400" />
                          <span className="text-neutral-550 font-sans text-xs">Awaiting compiler execution...</span>
                        </motion.div>
                      )}

                      {isConverting && (
                        <motion.div 
                          key="converting"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="flex-1 flex flex-col items-center justify-center text-center text-indigo-400 py-16 select-none gap-4"
                        >
                          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
                          <span className="text-[10px] tracking-wider uppercase font-bold text-neutral-400 font-sans">{statusText}</span>
                          <span className="text-lg font-bold text-white">{progress}%</span>
                        </motion.div>
                      )}

                      {isConverted && (
                        <motion.pre 
                          key="result"
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.4 }}
                          className="text-purple-300/90 whitespace-pre overflow-x-auto leading-relaxed"
                        >
                          {csharpCode}
                        </motion.pre>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Compilation Play Trigger Overlay */}
                {!isConverting && !isConverted && (
                  <div className="absolute inset-0 bg-neutral-950/65 backdrop-blur-[1.5px] flex items-center justify-center z-25">
                    <motion.button
                      whileHover={{ scale: 1.05, boxShadow: "0 0 30px rgba(99,102,241,0.4)" }}
                      whileTap={{ scale: 0.95 }}
                      onClick={handleStartConversion}
                      className="group flex items-center gap-3 bg-white text-black font-bold text-sm py-5 px-12 rounded-full shadow-2xl hover:scale-105 active:scale-95 transition-all duration-300 cursor-pointer tracking-wider"
                    >
                      <Play className="w-4 h-4 text-black fill-black animate-pulse" />
                      <span>Execute Compiler Agent</span>
                    </motion.button>
                  </div>
                )}

              </motion.div>

            </div>
          </section>

          {/* 3. Infinite Logo / Feature Marquee */}
          <section className="w-full py-14 bg-neutral-950 border-b border-neutral-900 overflow-hidden relative select-none">
            <div className="animate-marquee-left flex gap-24 items-center">
              {[
                "Database Schemas Mapped", "VBA Form parsing", "WPF UI Generation", "SQL dialect conversion",
                "Domain-Driven Design (DDD)", "EF Core scaffolding", "Oracle / SQL Server scripts", "MVVM Architecture Patterns",
                "Database Schemas Mapped", "VBA Form parsing", "WPF UI Generation", "SQL dialect conversion",
                "Domain-Driven Design (DDD)", "EF Core scaffolding", "Oracle / SQL Server scripts", "MVVM Architecture Patterns"
              ].map((text, idx) => (
                <div key={idx} className="flex items-center gap-3.5 text-sm font-mono text-neutral-455 uppercase tracking-widest whitespace-nowrap">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-500/50" />
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </section>

          {/* 4. Interactive 5-Layer Workspace Tabs */}
          <section id="timeline-tabs" className="w-full py-28 sm:py-36 md:py-48 px-6 sm:px-12 md:px-16 flex justify-center relative border-b border-neutral-900/80">
            <div className="max-w-6xl w-full flex flex-col items-center">
              
              {/* Header */}
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="text-center mb-24 max-w-2xl"
              >
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase mb-5">
                  <Layers className="w-4 h-4" />
                  <span>Pipeline Architecture</span>
                </div>
                <h2 className="text-4xl sm:text-6xl font-extrabold text-white tracking-wide mb-8">Interactive 5-Layer Workflow</h2>
                <p className="text-neutral-300 text-base leading-loose font-light">
                  Select a layer below to inspect how legacy components are parsed, verified, and mapped before final C# code generation.
                </p>
              </motion.div>

              {/* Tab Switcher Grid */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 sm:gap-6 w-full max-w-5xl mb-20 relative">
                {layersInfo.map((l, idx) => {
                  const Icon = l.icon;
                  const isActive = activeLayerTab === idx;
                  return (
                    <button
                      key={idx}
                      onClick={() => setActiveLayerTab(idx)}
                      className={`flex flex-col items-center gap-4 p-6 rounded-[20px] border transition-all duration-500 cursor-pointer relative overflow-hidden group ${
                        isActive 
                          ? "border-indigo-500/50 text-white" 
                          : "border-neutral-900 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-950/40"
                      }`}
                    >
                      {/* Framer Motion Active Tab Slider background */}
                      {isActive && (
                        <motion.div 
                          layoutId="activeLayerTabPill"
                          className="absolute inset-0 bg-neutral-900/60 shadow-[0_0_25px_rgba(99,102,241,0.25)] border border-indigo-500/30 rounded-[20px] z-0"
                          transition={{ type: "spring", stiffness: 350, damping: 28 }}
                        />
                      )}
                      
                      <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-300 relative z-10 ${
                        isActive ? "bg-indigo-500/10 text-indigo-400 scale-110" : "bg-neutral-900 text-neutral-550 group-hover:text-neutral-300"
                      }`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex flex-col items-center gap-0.5 relative z-10 text-center">
                        <span className="text-[10px] font-bold tracking-widest uppercase opacity-75">{l.layer}</span>
                        <span className="text-xs font-bold whitespace-nowrap mt-1">{l.title}</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Tab Content Box */}
              <motion.div 
                key={activeLayerTab}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="w-full bg-[#050506] border border-neutral-850 rounded-[32px] p-12 md:p-16 shadow-2xl relative overflow-hidden flex flex-col gap-12"
              >
                {/* Glow Backdrop */}
                <div 
                  className="absolute -top-1/2 -left-1/2 w-full h-full rounded-full blur-[140px] pointer-events-none transition-all duration-700"
                  style={{ background: layersInfo[activeLayerTab].glowColor }}
                />

                {/* Top Section */}
                <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-8 border-b border-neutral-900 pb-10">
                  <div className="flex flex-col gap-3">
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border w-fit ${layersInfo[activeLayerTab].badgeColor}`}>
                      <Sparkles className="w-3.5 h-3.5" />
                      {layersInfo[activeLayerTab].layer} Active
                    </span>
                    <h3 className="text-3xl font-extrabold tracking-wide text-white leading-snug">{layersInfo[activeLayerTab].title}</h3>
                  </div>
                  <div className="max-w-xl">
                    <p className="text-neutral-300 text-base leading-loose font-light">
                      {layersInfo[activeLayerTab].details}
                    </p>
                  </div>
                </div>

                {/* Bottom Section */}
                <div className="relative z-10 w-full grid grid-cols-1 md:grid-cols-2 gap-10 font-mono text-sm bg-black/40 p-10 rounded-2xl border border-neutral-900">
                  {/* Input Console */}
                  <div className="flex flex-col gap-4">
                    <div className="text-neutral-555 font-bold select-none font-sans uppercase tracking-widest text-[10px]">{layersInfo[activeLayerTab].inputLabel}</div>
                    <pre className="text-neutral-400/90 whitespace-pre overflow-x-auto leading-relaxed bg-[#0d0e15]/20 p-6 rounded-xl border border-neutral-900/60 hover:border-neutral-850 transition-colors duration-300">{layersInfo[activeLayerTab].inputContent}</pre>
                  </div>

                  {/* Output Console */}
                  <div className="border-t md:border-t-0 md:border-l border-neutral-900 pt-8 md:pt-0 md:pl-10 flex flex-col gap-4">
                    <div className="text-neutral-555 font-bold select-none font-sans uppercase tracking-widest text-[10px]">{layersInfo[activeLayerTab].outputLabel}</div>
                    <pre className="text-indigo-300/95 whitespace-pre overflow-x-auto leading-relaxed bg-[#0d0e15]/20 p-6 rounded-xl border border-neutral-900/60 hover:border-neutral-850 transition-colors duration-300">{layersInfo[activeLayerTab].outputContent}</pre>
                  </div>
                </div>

                {/* Workspace action link */}
                <div className="relative z-10 flex justify-end">
                  <Link 
                    href={layersInfo[activeLayerTab].link} 
                    className="inline-flex items-center gap-2 text-sm font-bold text-indigo-400 hover:text-indigo-300 group tracking-wide transition-colors"
                  >
                    <span>Open {layersInfo[activeLayerTab].layer} Workspace</span>
                    <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-300" />
                  </Link>
                </div>
              </motion.div>

            </div>
          </section>

          {/* 5. Technology Stack & Rules Section */}
          <section className="w-full py-28 sm:py-36 md:py-48 px-6 sm:px-12 md:px-16 flex justify-center bg-[#030303] border-b border-neutral-900/80">
            <div className="max-w-6xl w-full flex flex-col items-center">
              
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="text-center mb-24 max-w-2xl"
              >
                <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold tracking-wider uppercase mb-5">
                  <Code2 className="w-4 h-4" />
                  <span>Scaffold Architecture</span>
                </div>
                <h2 className="text-4xl sm:text-6xl font-extrabold text-white tracking-wide mb-8">Designed for Clean Code Standards</h2>
                <p className="text-neutral-300 text-base leading-loose font-light">
                  Generated code is built to last. Our parser outputs strictly clean, modular, and testable code adhering to industry standards.
                </p>
              </motion.div>

              {/* Rules Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-12 w-full">
                {[
                  { title: "Domain Driven Design (DDD)", desc: "WPF C# code is split cleanly into Domain, Application, Infrastructure, and UI projects to ensure modern enterprise architecture standards." },
                  { title: "Clean MVVM Separation", desc: "No hardcoded event handlers in WPF window files. Standardized ViewModel commands bind directly to reactive properties cleanly." },
                  { title: "Secure Config Files", desc: "All sensitive API keys, local ports, database credentials, and environments are ignored recursively, avoiding raw commits." }
                ].map((item, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.6, delay: idx * 0.15 }}
                    whileHover={{ y: -6, borderColor: "rgba(99, 102, 241, 0.45)" }}
                    className="bg-neutral-950/50 border border-neutral-900 rounded-[32px] p-12 flex flex-col hover:shadow-2xl hover:bg-neutral-900/10 transition-all duration-300 cursor-pointer"
                  >
                    <div className="text-lg sm:text-xl font-bold tracking-wide text-white mb-6">{item.title}</div>
                    <p className="text-sm sm:text-base text-neutral-300 font-light leading-loose">{item.desc}</p>
                  </motion.div>
                ))}
              </div>

            </div>
          </section>

          {/* 6. Live Studio Activity Console */}
          <section className="w-full py-28 sm:py-36 md:py-48 px-6 sm:px-12 md:px-16 flex justify-center bg-[#050506]/90 relative">
            <div className="max-w-4xl w-full flex flex-col gap-10">
              <motion.div 
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="flex items-center gap-2.5 text-indigo-400 text-xs font-bold tracking-wider uppercase"
              >
                <Terminal className="w-4 h-4" />
                <span>Live Studio activity console</span>
              </motion.div>
              <motion.h2 
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-3xl sm:text-5xl font-extrabold text-white tracking-wide"
              >
                Real-time pipeline monitoring status
              </motion.h2>
              
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7 }}
                className="bg-[#090a0f] border border-neutral-850 p-10 rounded-[32px] font-mono text-xs md:text-sm text-neutral-300 leading-relaxed shadow-2xl flex flex-col gap-6 min-h-[340px]"
              >
                <div className="flex items-center justify-between border-b border-neutral-900 pb-6 mb-4 select-none">
                  <span className="text-[11px] text-neutral-500 font-bold uppercase tracking-wider">vba_brain_orchestrator.log</span>
                  <div className="flex items-center gap-2 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full font-sans font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                    <span>Live Listener Active</span>
                  </div>
                </div>
                <div className="flex-1 flex flex-col gap-2.5 overflow-y-auto">
                  <AnimatePresence>
                    {logLines.map((line, idx) => (
                      <motion.div 
                        key={line + idx}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3 }}
                        className="flex items-start"
                      >
                        <span className="text-indigo-400 mr-2.5 select-none">&gt;</span>
                        <span className="break-all">{line}</span>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-indigo-400 mr-2.5 select-none">&gt;</span>
                    <span className="w-2.5 h-4 bg-indigo-400 animate-pulse"></span>
                  </div>
                </div>
              </motion.div>
            </div>
          </section>

        </main>

        {/* Footer */}
        <Footer />

      </div>
    </div>
  );
}
