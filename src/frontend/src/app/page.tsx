"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence, useScroll, useSpring, useInView } from "framer-motion";
import { 
  ArrowRight, DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, 
  Sparkles, ChevronRight, Play, RefreshCw,
  ArrowRightLeft, Layers, Terminal, Workflow,
  Monitor
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";

/* ─────────────────── Syntax Highlighting ─────────────────── */

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

function highlightVBA(code: string) {
  let html = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
  [/\bPublic\b/g, /\bSub\b/g, /\bDim\b/g, /\bAs\b/g, /\bSet\b/g, /\bIf\b/g, /\bThen\b/g, /\bEnd\b/g, /\bNot\b/g, /\bLong\b/g, /\bDatabase\b/g, /\bRecordset\b/g].forEach(kw => {
    html = html.replace(kw, (m) => `<span class="text-indigo-400 font-semibold">${m}</span>`);
  });
  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function highlightCSharp(code: string) {
  let html = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
  html = html.replace(/(\$".*?")/g, '<span class="text-amber-300">$1</span>');
  [/\bpublic\b/g, /\bprivate\b/g, /\busing\b/g, /\bvar\b/g, /\bawait\b/g, /\basync\b/g, /\bTask\b/g, /\bif\b/g, /\bnew\b/g, /\bnull\b/g, /\bvoid\b/g, /\blong\b/g].forEach(kw => {
    html = html.replace(kw, (m) => `<span class="text-purple-400 font-semibold">${m}</span>`);
  });
  html = html.replace(/(\/\/.*)$/gm, '<span class="text-emerald-500 font-normal">$1</span>');
  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function highlightCode(code: string, type: string) {
  let html = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (type === 'json') {
    html = html.replace(/(".*?")(\s*:)/g, '<span class="text-cyan-400 font-semibold">$1</span>$2');
    html = html.replace(/(:\s*)(".*?")/g, '$1<span class="text-amber-300">$2</span>');
    html = html.replace(/(:\s*)(\b\d+\b)/g, '$1<span class="text-indigo-400">$2</span>');
  } else if (type === 'sql') {
    [/\bSELECT\b/gi, /\bFROM\b/gi, /\bWHERE\b/gi, /\bAS\b/gi, /\bCASE\b/gi, /\bWHEN\b/gi, /\bTHEN\b/gi, /\bELSE\b/gi, /\bEND\b/gi].forEach(kw => {
      html = html.replace(kw, (m) => `<span class="text-indigo-400 font-semibold">${m}</span>`);
    });
    html = html.replace(/('.*?')/g, '<span class="text-amber-300">$1</span>');
  } else if (type === 'xml') {
    html = html.replace(/(&lt;\/?[a-zA-Z0-9:]+)/g, '<span class="text-indigo-400 font-semibold">$1</span>');
    html = html.replace(/(&gt;)/g, '<span class="text-indigo-400 font-semibold">$1</span>');
    html = html.replace(/(\s[a-zA-Z0-9:]+=)/g, '<span class="text-cyan-400">$1</span>');
    html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
  } else if (type === 'vba') {
    html = html.replace(/(^|[^"])(rem\s.*|'.*)$/gim, '$1<span class="text-emerald-500 font-normal">$2</span>');
    html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
    [/\bPublic\b/g, /\bSub\b/g, /\bDim\b/g, /\bAs\b/g, /\bSet\b/g, /\bIf\b/g, /\bThen\b/g, /\bEnd\b/g, /\bNot\b/g, /\bLong\b/g, /\bDatabase\b/g, /\bRecordset\b/g].forEach(kw => {
      html = html.replace(kw, (m) => `<span class="text-indigo-400 font-semibold">${m}</span>`);
    });
  } else if (type === 'csharp') {
    html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
    html = html.replace(/(\/\/.*)$/gm, '<span class="text-emerald-500 font-normal">$1</span>');
    [/\bpublic\b/g, /\bprivate\b/g, /\busing\b/g, /\bvar\b/g, /\bawait\b/g, /\basync\b/g, /\bTask\b/g, /\bif\b/g, /\bnew\b/g, /\bnull\b/g, /\bvoid\b/g, /\blong\b/g, /\bstring\b/g].forEach(kw => {
      html = html.replace(kw, (m) => `<span class="text-purple-400 font-semibold">${m}</span>`);
    });
  }
  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

/* ─────────────────── Typewriter Hook ─────────────────── */

function useTypewriter(texts: string[], speed = 60, pause = 2200) {
  const [display, setDisplay] = useState("");
  const [textIdx, setTextIdx] = useState(0);
  const [charIdx, setCharIdx] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const current = texts[textIdx];
    let timeout: ReturnType<typeof setTimeout>;

    if (!isDeleting && charIdx < current.length) {
      timeout = setTimeout(() => setCharIdx(c => c + 1), speed);
    } else if (!isDeleting && charIdx === current.length) {
      timeout = setTimeout(() => setIsDeleting(true), pause);
    } else if (isDeleting && charIdx > 0) {
      timeout = setTimeout(() => setCharIdx(c => c - 1), speed / 2);
    } else if (isDeleting && charIdx === 0) {
      setIsDeleting(false);
      setTextIdx(i => (i + 1) % texts.length);
    }

    setDisplay(current.substring(0, charIdx));
    return () => clearTimeout(timeout);
  }, [charIdx, isDeleting, textIdx, texts, speed, pause]);

  return display;
}

/* ─────────────────── Animated Counter ─────────────────── */

function AnimatedCounter({ value, suffix = "", prefix = "" }: { value: number; suffix?: string; prefix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const duration = 2000;
    const increment = value / (duration / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [inView, value]);

  return <span ref={ref}>{prefix}{count}{suffix}</span>;
}

/* ─────────────────── Log Renderer ─────────────────── */

function renderLogLine(line: string) {
  const regex = /^\[([:\d]+)\]\s+\[(Layer \d)\]\s+(.*)$/;
  const match = line.match(regex);
  if (match) {
    const [, time, layer, msg] = match;
    const layerColors: Record<string, string> = {
      "Layer 1": "text-cyan-400", "Layer 2": "text-purple-400",
      "Layer 3": "text-amber-400", "Layer 4": "text-emerald-400", "Layer 5": "text-rose-400"
    };
    const lc = layerColors[layer] || "text-indigo-400";
    const mc = (msg.includes("successful") || msg.includes("compiled")) ? "text-emerald-400 font-semibold" : "text-neutral-300";
    return (
      <div className="flex items-start">
        <span className="text-neutral-500 mr-2.5 select-none font-mono">&gt; [{time}]</span>
        <span className={`${lc} font-bold mr-2 select-none font-sans`}>[{layer}]</span>
        <span className={`${mc} break-all font-mono`}>{msg}</span>
      </div>
    );
  }
  return (
    <div className="flex items-start">
      <span className="text-indigo-400 mr-2.5 select-none font-mono">&gt;</span>
      <span className="text-neutral-400 break-all font-mono">{line}</span>
    </div>
  );
}

/* ═══════════════════ MAIN PAGE ═══════════════════ */

export default function LandingPage() {
  const [isMounted, setIsMounted] = useState(false);
  const [activeLayerTab, setActiveLayerTab] = useState(0);
  const [isConverting, setIsConverting] = useState(false);
  const [isConverted, setIsConverted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Idle");
  const [logLines, setLogLines] = useState<string[]>([
    "System initialized. gRPC migration listener active on port 50051.",
    "Database connection factory initialized: MongoDB local state active."
  ]);

  const typedText = useTypewriter([
    "in 5 Intelligent Layers",
    "with AI-Powered Agents",
    "to Modern WPF & C#",
  ], 70, 2500);

  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30, restDelta: 0.001 });

  useEffect(() => {
    setIsMounted(true);
    const logs = [
      "[Layer 1] Extracted AST JSON for F_Menu.frm (12 controls parsed).",
      "[Layer 2] Mapping logic graph: Form F_Menu ──► Query Q_ActiveProducts.",
      "[Layer 3] Converting Access SQL 'IIf(Stock <= 0, 0, Stock)' to PostgreSQL.",
      "[Layer 5] Generating Avalonia WPF View Model: F_MenuViewModel.cs",
      "[Layer 5] Compile validation: compile successful (0 errors, 2 warnings).",
      "[Layer 4] Seeded Excel specification workbook: DD_ScreenDefinition.xlsx",
      "[Layer 1] Parsed VBA Module Mod_CommonUtils: 14 functions mapped."
    ];
    let logIdx = 0;
    const interval = setInterval(() => {
      setLogLines(prev => {
        const next = [...prev, `[${new Date().toLocaleTimeString("vi-VN")}] ${logs[logIdx]}`];
        if (next.length > 8) next.shift();
        return next;
      });
      logIdx = (logIdx + 1) % logs.length;
    }, 4000);
    return () => clearInterval(interval);
  }, []);

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
      id: 0, layer: "Layer 1", title: "Source Extraction",
      shortDesc: "Extracts schema, forms & macros into AST JSON.",
      icon: DatabaseZap, link: "/layer1",
      details: "Parses database schema, UI forms, and VBA macros into structural AST JSON.",
      inputLabel: "MS Access Structure", inputType: "txt",
      inputContent: "📄 MS Access File\n  ├─ Tables: tblOrders\n  ├─ UI Form: F_OrderEntry\n  └─ VBA: Form_F_OrderEntry.cls",
      outputLabel: "extracted_ast.json", outputType: "json",
      outputContent: '{\n  "type": "Form",\n  "name": "F_OrderEntry",\n  "controls": [\n    { \n      "type": "TextBox", \n      "name": "txtOrderId" \n    }\n  ]\n}'
    },
    {
      id: 1, layer: "Layer 2", title: "Logic Analysis",
      shortDesc: "Maps entity relations and business logic.",
      icon: Bot, link: "/layer2",
      details: "Traces logic flows and DB queries to compile dependency graphs.",
      inputLabel: "vba_event_handlers.vba", inputType: "vba",
      inputContent: "Form_Open event trigger\nCommand click handlers\nVBA Recordset query dependencies",
      outputLabel: "dependency_graph.txt", outputType: "txt",
      outputContent: 'Form: F_OrderEntry\n  └─ triggers ClickEvent\n      └─ calls Q_GetOrder\n          └─ reads tblOrders (Col: CustName)'
    },
    {
      id: 2, layer: "Layer 4", title: "Excel Documentation",
      shortDesc: "Compiles specs into review Excel sheets.",
      icon: FileSpreadsheet, link: "/layer4",
      details: "Generates standardized technical spec workbooks.",
      inputLabel: "mapping_logic.txt", inputType: "txt",
      inputContent: "• Screen Form specifications\n• Database layout relations\n• Logic rule extraction arrays",
      outputLabel: "generated_specs.log", outputType: "txt",
      outputContent: "📊 BD_Specification.xlsx (12 Tables)\n📊 DD_ScreenDefinition.xlsx (8 Forms)\n📊 DD_MacroModule.xlsx (35 Macros)"
    },
    {
      id: 3, layer: "Layer 3", title: "SQL Conversion",
      shortDesc: "Translates Access SQL to enterprise SQL.",
      icon: Database, link: "/layer3",
      details: "Rewrites proprietary Access SQL into PostgreSQL or SQL Server.",
      inputLabel: "access_source.sql", inputType: "sql",
      inputContent: "SELECT OrderID, \n  IIf(Status='A', \n      'Active', 'Inactive') AS State\nFROM Orders;",
      outputLabel: "postgresql_target.sql", outputType: "sql",
      outputContent: "SELECT OrderID,\n  CASE WHEN Status = 'A' \n       THEN 'Active'\n       ELSE 'Inactive' \n  END AS State\nFROM Orders;"
    },
    {
      id: 4, layer: "Layer 5", title: "C# & WPF Generation",
      shortDesc: "Compiles WPF views and C# MVVM logic.",
      icon: Cpu, link: "/layer5",
      details: "Generates WPF XAML layouts and MVVM C# backend code.",
      inputLabel: "ModernView.xaml", inputType: "xml",
      inputContent: '<TextBox Text="{Binding OrderNo}" />\n<Button Content="Process"\n  Command="{Binding ProcessCmd}" />',
      outputLabel: "ViewModel.cs", outputType: "csharp",
      outputContent: "public ICommand ProcessCmd { get; }\nprivate void ExecuteProcess()\n{\n    _orderService.Process(OrderNo);\n}"
    }
  ];

  const fadeUp = {
    hidden: { opacity: 0, y: 40 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] as const } }
  };

  const stagger = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.1 } }
  };

  return (
    <div className="flex-1 w-full min-h-screen bg-neutral-50 dark:bg-[#030303] text-neutral-800 dark:text-neutral-200 font-sans selection:bg-indigo-500/30 selection:text-white relative overflow-x-hidden scroll-smooth transition-colors duration-300">
      
      {/* Scroll Progress */}
      <motion.div className="fixed top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-indigo-600 via-purple-500 to-indigo-600 origin-left z-50" style={{ scaleX }} />

      <style>{`
        .grid-mesh {
          background-image: radial-gradient(circle at 1px 1px, rgba(0, 0, 0, 0.02) 1px, transparent 0);
          background-size: 28px 28px;
        }
        .dark .grid-mesh {
          background-image: radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.012) 1px, transparent 0);
        }
        .radar-scan-line {
          background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.15) 50%, transparent 100%);
          background-size: 100% 200px;
          animation: scanVertical 2.5s linear infinite;
        }
        .animate-marquee-left {
          display: flex;
          width: max-content;
          animation: marqueeScroll 40s linear infinite;
        }
        @keyframes scanVertical {
          0% { background-position: 0 -200px; }
          100% { background-position: 0 400px; }
        }
        @keyframes marqueeScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .terminal-cursor {
          display: inline-block;
          width: 8px;
          height: 15px;
          background-color: #6366f1;
          animation: terminalBlink 1s step-end infinite;
          vertical-align: middle;
        }
        @keyframes terminalBlink {
          50% { opacity: 0; }
        }
        .typewriter-cursor {
          display: inline-block;
          width: 3px;
          height: 1em;
          background: currentColor;
          margin-left: 2px;
          animation: terminalBlink 0.8s step-end infinite;
          vertical-align: text-bottom;
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
      `}</style>

      {/* Background Orbs */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <motion.div 
          animate={{ y: [0, -30, 0], x: [0, 20, 0], scale: [1, 1.05, 1] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[5%] left-[10%] w-[300px] sm:w-[500px] h-[300px] sm:h-[500px] rounded-full bg-indigo-500/10 blur-[120px] sm:blur-[160px]"
        />
        <motion.div 
          animate={{ y: [0, 30, 0], x: [0, -25, 0], scale: [1, 0.95, 1] }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-[20%] right-[5%] w-[350px] sm:w-[600px] h-[350px] sm:h-[600px] rounded-full bg-purple-500/10 blur-[130px] sm:blur-[190px]"
        />
        <div className="absolute inset-0 grid-mesh opacity-80" />
      </div>

      <div className="relative z-10 flex flex-col w-full min-h-screen">
        <Header />

        <main className="flex-1 w-full flex flex-col">
          
          {/* ════════════ HERO ════════════ */}
          <section className="w-full pt-28 sm:pt-40 pb-24 sm:pb-36 px-8 sm:px-16 md:px-20 flex justify-center border-b border-neutral-200 dark:border-neutral-900/85 relative">
            <motion.div 
              initial="hidden" animate="visible" variants={stagger}
              className="max-w-5xl w-full flex flex-col items-center text-center"
            >
              {/* Badge */}
              <motion.div variants={fadeUp} className="mb-8">
                <span className="inline-flex items-center gap-2.5 text-xs font-bold tracking-[0.2em] uppercase text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 px-4 py-2 rounded-full">
                  <Sparkles className="w-3.5 h-3.5" />
                  AI-Powered Migration Engine
                </span>
              </motion.div>

              {/* Heading with Typewriter */}
              <motion.h1 
                variants={fadeUp}
                className="text-4xl sm:text-6xl md:text-7xl lg:text-[5.5rem] font-extrabold tracking-tight text-neutral-900 dark:text-white leading-[1.1] mb-8"
              >
                Rebuild Legacy Access
                <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-500 to-indigo-600 dark:from-indigo-400 dark:via-purple-400 dark:to-indigo-400">
                  {typedText}
                  <span className="typewriter-cursor" />
                </span>
              </motion.h1>
              
              {/* Subtitle — short & punchy */}
              <motion.p 
                variants={fadeUp}
                className="text-lg sm:text-xl text-neutral-500 dark:text-neutral-400 max-w-2xl mx-auto mb-16 leading-relaxed"
              >
                Multi-agent AI pipeline that translates MS Access into modern WPF C# applications with compile-safe accuracy.
              </motion.p>
              
              {/* CTA Buttons */}
              <motion.div variants={fadeUp} className="flex flex-col sm:flex-row items-center justify-center gap-5 mb-32 w-full max-w-xl mx-auto">
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} className="w-full sm:w-auto">
                  <Link href="/layer1" className="w-full sm:w-auto inline-flex items-center justify-center gap-3 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white font-semibold py-4 px-10 text-base rounded-full shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all duration-300 whitespace-nowrap">
                    Get Started
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </motion.div>
                <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} className="w-full sm:w-auto">
                  <Link href="#layers" className="w-full sm:w-auto inline-flex items-center justify-center bg-white dark:bg-white/5 text-neutral-800 dark:text-white font-semibold py-4 px-10 text-base rounded-full border border-neutral-200 dark:border-white/10 hover:bg-neutral-100 dark:hover:bg-white/10 shadow-sm transition-all duration-300 whitespace-nowrap">
                    Explore Layers
                  </Link>
                </motion.div>
              </motion.div>

              {/* Live Transformation Bridge */}
              <motion.div 
                variants={fadeUp}
                className="w-full max-w-5xl bg-white/80 dark:bg-neutral-950/45 backdrop-blur-md border border-neutral-200 dark:border-neutral-800 rounded-3xl p-10 sm:p-16 relative overflow-hidden shadow-xl dark:shadow-2xl"
              >
                <div className="absolute top-1/2 left-[25%] right-[25%] h-[1px] bg-gradient-to-r from-transparent via-indigo-300 dark:via-indigo-700 to-transparent -translate-y-1/2 hidden md:block" />

                <div className="flex flex-col md:flex-row items-center justify-between gap-10 md:gap-16 relative z-10">
                  {/* Legacy Stack */}
                  <motion.div whileHover={{ y: -4 }} className="flex flex-col items-center gap-6 bg-neutral-50/80 dark:bg-neutral-900/30 border border-neutral-200 dark:border-neutral-800 p-8 rounded-2xl w-full md:w-[320px] transition-all duration-300">
                    <span className="text-xs font-bold text-neutral-400 tracking-[0.2em] uppercase">Legacy Stack</span>
                    <div className="flex items-center gap-4 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-200 dark:border-indigo-900/30 shrink-0">
                        <DatabaseZap className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white">Access Database</div>
                        <div className="text-xs text-neutral-500 font-mono">.accdb / .mdb</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-200 dark:border-indigo-900/30 shrink-0">
                        <FileSpreadsheet className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white">VBA Modules</div>
                        <div className="text-xs text-neutral-500 font-mono">Macros & Functions</div>
                      </div>
                    </div>
                  </motion.div>

                  {/* AI Core */}
                  <div className="relative flex flex-col items-center select-none shrink-0 py-4">
                    <motion.div 
                      whileHover={{ scale: 1.1 }}
                      animate={{ boxShadow: ["0 0 0 0 rgba(99,102,241,0.3)", "0 0 0 20px rgba(99,102,241,0)", "0 0 0 0 rgba(99,102,241,0)"] }}
                      transition={{ boxShadow: { duration: 2, repeat: Infinity, ease: "easeOut" } }}
                      className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg cursor-pointer"
                    >
                      <Bot className="w-9 h-9 text-white" />
                    </motion.div>
                    <div className="text-sm font-bold text-neutral-900 dark:text-white mt-3 tracking-wider uppercase">vba_brain</div>
                    <div className="text-xs text-indigo-600 dark:text-indigo-400 font-mono uppercase">Pipeline Active</div>
                  </div>

                  {/* Modern Target */}
                  <motion.div whileHover={{ y: -4 }} className="flex flex-col items-center gap-6 bg-neutral-50/80 dark:bg-neutral-900/30 border border-neutral-200 dark:border-neutral-800 p-8 rounded-2xl w-full md:w-[320px] transition-all duration-300">
                    <span className="text-xs font-bold text-neutral-400 tracking-[0.2em] uppercase">Modern Target</span>
                    <div className="flex items-center gap-4 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-200 dark:border-indigo-900/30 shrink-0">
                        <Cpu className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white">Avalonia WPF</div>
                        <div className="text-xs text-neutral-500 font-mono">C# & MVVM</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-200 dark:border-indigo-900/30 shrink-0">
                        <Database className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white">PostgreSQL</div>
                        <div className="text-xs text-neutral-500 font-mono">Optimized Dialect</div>
                      </div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>
            </motion.div>
          </section>

          {/* ════════════ PLAYGROUND ════════════ */}
          <section id="playground" className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center border-b border-neutral-200 dark:border-neutral-900/80 bg-neutral-100/40 dark:bg-[#050506]/80 relative">
            <div className="max-w-5xl w-full flex flex-col items-center gap-16">
              
              <motion.div 
                initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-center max-w-2xl"
              >
                <div className="inline-flex items-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Interactive Playground</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight mb-5 leading-tight">
                  VBA → C# in real time
                </h2>
                <p className="text-neutral-500 dark:text-neutral-400 text-base sm:text-lg leading-relaxed">
                  Watch legacy code transform into modern C# with EF Core.
                </p>
              </motion.div>

              {/* Code Editor */}
              <motion.div 
                initial={{ opacity: 0, y: 40, scale: 0.98 }} whileInView={{ opacity: 1, y: 0, scale: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-5xl bg-[#090a0f] border border-neutral-200 dark:border-neutral-800 rounded-2xl overflow-hidden shadow-2xl relative"
              >
                {/* Top Bar */}
                <div className="flex items-center justify-between px-5 py-3.5 bg-[#0d0e15] border-b border-neutral-900/80 select-none">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                    <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                    <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                    <span className="text-sm font-mono text-neutral-500 ml-3">vba_brain_compiler.py</span>
                  </div>
                  {isConverted && (
                    <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={handleResetConversion} 
                      className="text-sm text-neutral-300 hover:text-white bg-neutral-900 border border-neutral-800 hover:border-neutral-700 px-4 py-1.5 rounded-full transition-all cursor-pointer font-semibold">
                      Reset
                    </motion.button>
                  )}
                </div>

                {/* Code Panels */}
                <div className="grid grid-cols-1 md:grid-cols-2 relative font-mono text-sm">
                  {/* VBA */}
                  <div className="p-6 sm:p-8 bg-[#0b0c10] flex flex-col border-b md:border-b-0 md:border-r border-neutral-900">
                    <div className="flex items-center justify-between pb-3 border-b border-neutral-900/60 mb-5 select-none">
                      <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider font-sans">VBA Source</span>
                      <span className="text-xs font-mono text-cyan-400/80 bg-cyan-500/5 px-2 py-0.5 rounded border border-cyan-500/10">vba</span>
                    </div>
                    <div className="flex font-mono text-sm">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900/80 text-right select-none leading-7">
                        {vbaCode.split('\n').map((_, idx) => (<div key={idx} className="h-7">{idx + 1}</div>))}
                      </div>
                      <pre className="pl-4 text-cyan-300/90 overflow-x-auto flex-1 leading-7">{highlightVBA(vbaCode)}</pre>
                    </div>
                  </div>

                  {/* C# */}
                  <div className="p-6 sm:p-8 bg-[#06070a] flex flex-col relative min-h-[340px]">
                    <div className="flex items-center justify-between pb-3 border-b border-neutral-900/60 mb-5 select-none">
                      <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider font-sans">C# Target</span>
                      <span className="text-xs font-mono text-purple-400/80 bg-purple-400/5 px-2 py-0.5 rounded border border-purple-400/10">c#</span>
                    </div>
                    {isConverting && <div className="absolute inset-0 z-10 radar-scan-line pointer-events-none" />}
                    <AnimatePresence mode="wait">
                      {!isConverting && !isConverted && (
                        <motion.div key="awaiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                          className="flex-1 flex flex-col items-center justify-center text-center text-neutral-600 py-12 select-none">
                          <Cpu className="w-8 h-8 mb-3 opacity-30 animate-pulse text-indigo-400" />
                          <span className="text-neutral-500 font-sans text-sm">Awaiting execution...</span>
                        </motion.div>
                      )}
                      {isConverting && (
                        <motion.div key="converting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                          className="flex-1 flex flex-col items-center justify-center text-center text-indigo-400 py-12 select-none gap-3">
                          <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
                          <span className="text-sm tracking-wider uppercase font-bold text-neutral-400 font-sans">{statusText}</span>
                          <span className="text-lg font-bold text-white">{progress}%</span>
                        </motion.div>
                      )}
                      {isConverted && (
                        <motion.div key="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
                          className="flex font-mono text-sm">
                          <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900/80 text-right select-none leading-7">
                            {csharpCode.split('\n').map((_, idx) => (<div key={idx} className="h-7">{idx + 1}</div>))}
                          </div>
                          <pre className="pl-4 text-purple-300/95 overflow-x-auto flex-1 leading-7">{highlightCSharp(csharpCode)}</pre>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Play Button Overlay */}
                {!isConverting && !isConverted && (
                  <div className="absolute inset-0 bg-neutral-950/50 dark:bg-neutral-950/65 backdrop-blur-[2px] flex items-center justify-center z-20">
                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleStartConversion}
                      className="group flex items-center gap-3 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white font-semibold text-sm py-3.5 px-8 rounded-full shadow-lg shadow-indigo-500/25 transition-all duration-300 cursor-pointer tracking-wider uppercase">
                      <Play className="w-4 h-4 text-white fill-white" />
                      <span>Run Compiler Agent</span>
                    </motion.button>
                  </div>
                )}
              </motion.div>
            </div>
          </section>

          {/* ════════════ MARQUEE ════════════ */}
          <section className="w-full py-10 bg-neutral-100 dark:bg-neutral-950 border-b border-neutral-200 dark:border-neutral-900 overflow-hidden select-none">
            <div className="animate-marquee-left flex gap-20 items-center">
              {[
                "Database Mapping", "VBA Parsing", "WPF Generation", "SQL Conversion",
                "DDD Architecture", "EF Core", "PostgreSQL", "MVVM Patterns",
                "Database Mapping", "VBA Parsing", "WPF Generation", "SQL Conversion",
                "DDD Architecture", "EF Core", "PostgreSQL", "MVVM Patterns"
              ].map((text, idx) => (
                <div key={idx} className="flex items-center gap-4 text-xs font-mono text-neutral-500 dark:text-neutral-500 uppercase tracking-[0.15em] whitespace-nowrap">
                  <Sparkles className="w-3 h-3 text-indigo-500/40" />
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </section>

          {/* ════════════ MIGRATION JOURNEY ════════════ */}
          <section className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center bg-white dark:bg-[#030303] border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-4xl w-full flex flex-col items-center">
              
              <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.7 }}
                className="text-center mb-20 max-w-2xl">
                <div className="inline-flex items-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <Workflow className="w-4 h-4" />
                  <span>Migration Flow</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight leading-tight">
                  5 Steps to Modernize
                </h2>
              </motion.div>

              {/* Timeline */}
              <div className="relative w-full flex flex-col gap-16 sm:gap-20 pl-12 sm:pl-20 border-l-2 border-neutral-200 dark:border-neutral-800">
                {[
                  { step: "01", title: "AST Extraction", badge: "Layer 1", desc: "Scan tables, forms & VBA into structured JSON." },
                  { step: "02", title: "Dependency Mapping", badge: "Layer 2", desc: "Build complete application logic flow graphs." },
                  { step: "03", title: "Spec Generation", badge: "Layer 4", desc: "Auto-generate technical Excel workbooks." },
                  { step: "04", title: "SQL Conversion", badge: "Layer 3", desc: "Rewrite Access SQL to PostgreSQL." },
                  { step: "05", title: "WPF Synthesis", badge: "Layer 5", desc: "Compile XAML views & C# MVVM code." }
                ].map((item, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.5, delay: idx * 0.08 }}
                    className="relative group"
                  >
                    <div className="absolute left-[-54px] sm:left-[-90px] top-1.5 w-5 h-5 rounded-full border-2 border-indigo-600 dark:border-indigo-500 bg-white dark:bg-[#030303] group-hover:bg-indigo-600 dark:group-hover:bg-indigo-500 transition-all duration-300 shadow-sm" />
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-4">
                        <span className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/45 px-2.5 py-1 rounded border border-indigo-100 dark:border-indigo-900/30">
                          {item.badge}
                        </span>
                        <span className="text-xl font-black text-neutral-200 dark:text-neutral-800 font-mono">{item.step}</span>
                      </div>
                      <h3 className="text-lg font-bold text-neutral-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors duration-300">
                        {item.title}
                      </h3>
                      <p className="text-sm text-neutral-500 dark:text-neutral-400 leading-relaxed max-w-lg">
                        {item.desc}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* ════════════ INTERACTIVE LAYERS ════════════ */}
          <section id="layers" className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center relative border-b border-neutral-200 dark:border-neutral-900/80 bg-white dark:bg-[#030303]">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-center mb-16 max-w-2xl">
                <div className="inline-flex items-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <Layers className="w-4 h-4" />
                  <span>Pipeline Architecture</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
                  Explore Each Layer
                </h2>
              </motion.div>

              {/* Tab Switcher */}
              <motion.div initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 w-full max-w-4xl mb-16 relative">
                {layersInfo.map((l, idx) => {
                  const Icon = l.icon;
                  const isActive = activeLayerTab === idx;
                  return (
                    <button key={idx} onClick={() => setActiveLayerTab(idx)}
                      className={`flex items-center gap-2.5 px-5 py-3 rounded-xl border transition-all duration-300 cursor-pointer text-sm font-semibold relative overflow-hidden ${
                        isActive 
                          ? "border-indigo-300 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10" 
                          : "border-neutral-200 dark:border-neutral-800 text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900/40"
                      }`}>
                      <Icon className="w-4 h-4" />
                      <span className="hidden sm:inline">{l.layer}:</span> {l.title}
                    </button>
                  );
                })}
              </motion.div>

              {/* Tab Content */}
              <motion.div 
                key={activeLayerTab}
                initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="w-full bg-neutral-50 dark:bg-[#050506] border border-neutral-200 dark:border-neutral-800 rounded-3xl p-8 sm:p-12 shadow-lg dark:shadow-2xl relative overflow-hidden flex flex-col gap-10"
              >
                {/* Top Info */}
                <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 border-b border-neutral-200 dark:border-neutral-900 pb-8">
                  <div className="flex flex-col gap-3">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border w-fit bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20">
                      <Sparkles className="w-3 h-3" />
                      {layersInfo[activeLayerTab].layer} Active
                    </span>
                    <h3 className="text-2xl font-bold text-neutral-900 dark:text-white">{layersInfo[activeLayerTab].title}</h3>
                  </div>
                  <p className="text-neutral-500 dark:text-neutral-400 text-sm leading-relaxed max-w-md">
                    {layersInfo[activeLayerTab].details}
                  </p>
                </div>

                {/* Mock IDE Grid */}
                <div className="relative z-10 w-full grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Input */}
                  <div className="flex flex-col rounded-xl border border-neutral-200 dark:border-neutral-900 bg-[#07080b]/95 shadow-md overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 bg-[#0d0e12] border-b border-neutral-900/80 select-none">
                      <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider font-sans">{layersInfo[activeLayerTab].inputLabel}</span>
                      <span className="text-xs font-mono text-neutral-500 uppercase bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">{layersInfo[activeLayerTab].inputType}</span>
                    </div>
                    <div className="flex p-5 font-mono text-sm leading-7 overflow-x-auto">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900 text-right select-none leading-7">
                        {layersInfo[activeLayerTab].inputContent.split('\n').map((_, idx) => (<div key={idx} className="h-7">{idx + 1}</div>))}
                      </div>
                      <pre className="pl-4 text-neutral-300 overflow-x-auto flex-1 w-full leading-7">
                        {highlightCode(layersInfo[activeLayerTab].inputContent, layersInfo[activeLayerTab].inputType)}
                      </pre>
                    </div>
                  </div>

                  {/* Output */}
                  <div className="flex flex-col rounded-xl border border-neutral-200 dark:border-neutral-900 bg-[#07080b]/95 shadow-md overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 bg-[#0d0e12] border-b border-neutral-900/80 select-none">
                      <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider font-sans">{layersInfo[activeLayerTab].outputLabel}</span>
                      <span className="text-xs font-mono text-indigo-400 uppercase bg-indigo-500/5 px-2 py-0.5 rounded border border-indigo-500/10">{layersInfo[activeLayerTab].outputType}</span>
                    </div>
                    <div className="flex p-5 font-mono text-sm leading-7 overflow-x-auto">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900 text-right select-none leading-7">
                        {layersInfo[activeLayerTab].outputContent.split('\n').map((_, idx) => (<div key={idx} className="h-7">{idx + 1}</div>))}
                      </div>
                      <pre className="pl-4 text-indigo-300/95 overflow-x-auto flex-1 w-full leading-7">
                        {highlightCode(layersInfo[activeLayerTab].outputContent, layersInfo[activeLayerTab].outputType)}
                      </pre>
                    </div>
                  </div>
                </div>

                {/* Link */}
                <div className="relative z-10 flex justify-end">
                  <Link href={layersInfo[activeLayerTab].link} 
                    className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 group tracking-wide transition-colors">
                    Open {layersInfo[activeLayerTab].layer} Workspace
                    <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform duration-300" />
                  </Link>
                </div>
              </motion.div>
            </div>
          </section>

          {/* ════════════ METRICS ════════════ */}
          <section className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center bg-neutral-50 dark:bg-[#050506]/70 border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.7 }}
                className="text-center mb-20">
                <div className="inline-flex items-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <Monitor className="w-4 h-4" />
                  <span>Pipeline Scale</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
                  Built for Enterprise
                </h2>
              </motion.div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 w-full">
                {[
                  { value: 99.8, suffix: "%", label: "Accuracy" },
                  { value: 10, suffix: "x", label: "Faster" },
                  { value: 500, suffix: "k+", label: "Lines Parsed" },
                  { value: 0, prefix: "Zero", suffix: "", label: "Data Leaks" }
                ].map((metric, idx) => (
                  <motion.div key={idx}
                    initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }} transition={{ duration: 0.5, delay: idx * 0.08 }}
                    className="flex flex-col p-8 sm:p-10 bg-white dark:bg-[#090a0f] border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-sm text-center gap-3 hover:shadow-lg hover:border-indigo-200 dark:hover:border-indigo-500/20 transition-all duration-300"
                  >
                    <span className="text-3xl sm:text-4xl md:text-5xl font-black text-indigo-600 dark:text-indigo-400 tracking-tight">
                      {metric.prefix ? metric.prefix : <AnimatedCounter value={metric.value} suffix={metric.suffix} />}
                    </span>
                    <span className="text-sm font-bold text-neutral-900 dark:text-white">{metric.label}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* ════════════ COMPARISON TABLE ════════════ */}
          <section className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center bg-white dark:bg-[#030303] border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-4xl w-full flex flex-col items-center">
              
              <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.7 }}
                className="text-center mb-16">
                <div className="inline-flex items-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Why vba_brain</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
                  Manual vs. Automated
                </h2>
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.6 }}
                className="w-full overflow-x-auto rounded-2xl border border-neutral-200 dark:border-neutral-800 shadow-sm">
                <table className="w-full text-left border-collapse text-sm font-sans min-w-[550px]">
                  <thead>
                    <tr className="bg-neutral-100/50 dark:bg-neutral-900/40 border-b border-neutral-200 dark:border-neutral-800">
                      <th className="py-5 px-6 font-bold text-neutral-900 dark:text-white">Feature</th>
                      <th className="py-5 px-6 font-bold text-neutral-500">Manual</th>
                      <th className="py-5 px-6 font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50/30 dark:bg-indigo-950/10">vba_brain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { metric: "Speed", manual: "Weeks per screen", auto: "Seconds per module" },
                      { metric: "Accuracy", manual: "Human errors", auto: "99.8% precision" },
                      { metric: "Docs", manual: "Sparse markdown", auto: "Auto Excel sheets" },
                      { metric: "Architecture", manual: "Inconsistent", auto: "DDD / MVVM" },
                      { metric: "SQL Validation", manual: "Manual check", auto: "Real-time compiler" }
                    ].map((row, idx) => (
                      <tr key={idx} className="border-b border-neutral-200 dark:border-neutral-800 last:border-0 hover:bg-neutral-50/50 dark:hover:bg-neutral-900/10 transition-colors">
                        <td className="py-5 px-6 font-bold text-neutral-900 dark:text-white">{row.metric}</td>
                        <td className="py-5 px-6 text-neutral-500">{row.manual}</td>
                        <td className="py-5 px-6 text-indigo-600 dark:text-indigo-400 bg-indigo-50/10 dark:bg-indigo-950/5 font-semibold">{row.auto}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </motion.div>
            </div>
          </section>

          {/* ════════════ LIVE CONSOLE ════════════ */}
          <section className="w-full py-28 sm:py-40 px-8 sm:px-16 md:px-20 flex justify-center bg-neutral-100/30 dark:bg-[#050506]/90 border-b border-neutral-200 dark:border-neutral-900/80 relative">
            <div className="max-w-5xl w-full flex flex-col gap-16">
              
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }}
                className="text-center">
                <div className="inline-flex items-center justify-center gap-3 text-indigo-600 dark:text-indigo-400 text-xs font-bold tracking-[0.2em] uppercase mb-5">
                  <Terminal className="w-4 h-4" />
                  <span>Live Console</span>
                </div>
                <h2 className="text-3xl sm:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
                  Real-time Pipeline Monitor
                </h2>
              </motion.div>
              
              <motion.div 
                initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="bg-[#090a0f] border border-neutral-200 dark:border-neutral-800 p-8 sm:p-12 rounded-2xl font-mono text-sm text-neutral-300 leading-relaxed shadow-xl dark:shadow-2xl flex flex-col gap-6 min-h-[340px]"
              >
                <div className="flex items-center justify-between border-b border-neutral-900/80 pb-4 mb-3 select-none">
                  <span className="text-xs text-neutral-500 font-bold uppercase tracking-wider">orchestrator.log</span>
                  <div className="flex items-center gap-3 text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50/10 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-3 py-1.5 rounded-full font-sans font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                    <span>Live</span>
                  </div>
                </div>
                <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-2">
                  <AnimatePresence>
                    {logLines.map((line, idx) => (
                      <motion.div key={line + idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
                        {renderLogLine(line)}
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  <div className="flex items-center gap-1 mt-1 select-none">
                    <span className="text-indigo-400 mr-2.5 select-none font-mono">&gt;</span>
                    <span className="terminal-cursor" />
                  </div>
                </div>
              </motion.div>
            </div>
          </section>

        </main>

        <Footer />
      </div>
    </div>
  );
}
