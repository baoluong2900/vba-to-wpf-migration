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

// Syntax highlighting helpers
function highlightVBA(code: string) {
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Strings
  html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');

  // Keywords
  const keywords = [
    /\bPublic\b/g, /\bSub\b/g, /\bDim\b/g, /\bAs\b/g, /\bSet\b/g,
    /\bIf\b/g, /\bThen\b/g, /\bEnd\b/g, /\bNot\b/g, /\bLong\b/g, /\bDatabase\b/g, /\bRecordset\b/g
  ];
  keywords.forEach(kw => {
    html = html.replace(kw, (m) => `<span class="text-indigo-400 font-semibold">${m}</span>`);
  });

  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function highlightCSharp(code: string) {
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Strings
  html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
  html = html.replace(/(\$".*?")/g, '<span class="text-amber-300">$1</span>');

  // Keywords
  const keywords = [
    /\bpublic\b/g, /\bprivate\b/g, /\busing\b/g, /\bvar\b/g, /\bawait\b/g, /\basync\b/g,
    /\bTask\b/g, /\bif\b/g, /\bnew\b/g, /\bnull\b/g, /\bvoid\b/g, /\blong\b/g
  ];
  keywords.forEach(kw => {
    html = html.replace(kw, (m) => `<span class="text-purple-450 font-semibold">${m}</span>`);
  });

  // Comments
  html = html.replace(/(\/\/.*)$/gm, '<span class="text-emerald-500 font-normal">$1</span>');

  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function highlightCode(code: string, type: string) {
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  if (type === 'json') {
    html = html.replace(/(".*?")(\s*:)/g, '<span class="text-cyan-400 font-semibold">$1</span>$2');
    html = html.replace(/(:\s*)(".*?")/g, '$1<span class="text-amber-300">$2</span>');
    html = html.replace(/(:\s*)(\b\d+\b)/g, '$1<span class="text-indigo-400">$2</span>');
  } else if (type === 'sql') {
    const keywords = [
      /\bSELECT\b/gi, /\bFROM\b/gi, /\bWHERE\b/gi, /\bAS\b/gi, /\bCASE\b/gi,
      /\bWHEN\b/gi, /\bTHEN\b/gi, /\bELSE\b/gi, /\bEND\b/gi
    ];
    keywords.forEach(kw => {
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
    const keywords = [
      /\bPublic\b/g, /\bSub\b/g, /\bDim\b/g, /\bAs\b/g, /\bSet\b/g,
      /\bIf\b/g, /\bThen\b/g, /\bEnd\b/g, /\bNot\b/g, /\bLong\b/g, /\bDatabase\b/g, /\bRecordset\b/g
    ];
    keywords.forEach(kw => {
      html = html.replace(kw, (m) => `<span class="text-indigo-400 font-semibold">${m}</span>`);
    });
  } else if (type === 'csharp') {
    html = html.replace(/(".*?")/g, '<span class="text-amber-300">$1</span>');
    html = html.replace(/(\/\/.*)$/gm, '<span class="text-emerald-500 font-normal">$1</span>');
    const keywords = [
      /\bpublic\b/g, /\bprivate\b/g, /\busing\b/g, /\bvar\b/g, /\bawait\b/g, /\basync\b/g,
      /\bTask\b/g, /\bif\b/g, /\bnew\b/g, /\bnull\b/g, /\bvoid\b/g, /\blong\b/g, /\bstring\b/g
    ];
    keywords.forEach(kw => {
      html = html.replace(kw, (m) => `<span class="text-purple-400 font-semibold">${m}</span>`);
    });
  }

  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function renderLogLine(line: string) {
  const regex = /^\[([\d:]+)\]\s+\[(Layer \d)\]\s+(.*)$/;
  const match = line.match(regex);
  if (match) {
    const [_, time, layer, msg] = match;
    let layerColor = "text-indigo-400";
    if (layer === "Layer 1") layerColor = "text-cyan-400";
    else if (layer === "Layer 2") layerColor = "text-purple-450";
    else if (layer === "Layer 3") layerColor = "text-emerald-400";
    else if (layer === "Layer 4") layerColor = "text-amber-400";
    else if (layer === "Layer 5") layerColor = "text-rose-400";

    let msgColor = "text-neutral-300";
    if (msg.includes("successful") || msg.includes("compiled")) {
      msgColor = "text-emerald-400 font-semibold";
    }

    return (
      <div className="flex items-start">
        <span className="text-neutral-500 mr-2.5 select-none font-mono">&gt; [{time}]</span>
        <span className={`${layerColor} font-bold mr-2 select-none font-sans`}>[{layer}]</span>
        <span className={`${msgColor} break-all font-mono`}>{msg}</span>
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
      shortDesc: "Extracts database schema, forms, and macros into AST JSON.",
      icon: DatabaseZap,
      link: "/layer1",
      color: "indigo",
      badgeColor: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20",
      glowColor: "rgba(99, 102, 241, 0.05)",
      details: "Extracts database schema, UI form parameters, and macros into structural AST JSON.",
      inputLabel: "MS Access Database Structure",
      inputType: "txt",
      inputContent: "📄 MS Access File\n  ├─ Tables: tblOrders\n  ├─ UI Form: F_OrderEntry\n  └─ VBA: Form_F_OrderEntry.cls",
      outputLabel: "vba_brain_extracted_ast.json",
      outputType: "json",
      outputContent: '{\n  "type": "Form",\n  "name": "F_OrderEntry",\n  "controls": [\n    { \n      "type": "TextBox", \n      "name": "txtOrderId" \n    }\n  ]\n}'
    },
    {
      id: 1,
      layer: "Layer 2",
      title: "Logic Analysis",
      shortDesc: "Maps entity relations and isolates code business logic.",
      icon: Bot,
      link: "/layer2",
      color: "indigo",
      badgeColor: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20",
      glowColor: "rgba(99, 102, 241, 0.05)",
      details: "Traces logic event flows and database queries to compile dependency graphs.",
      inputLabel: "extracted_ast_elements.vba",
      inputType: "vba",
      inputContent: "Form_Open event trigger\nCommand click handlers\nVBA Recordset query dependencies",
      outputLabel: "dependency_logic_graph.txt",
      outputType: "txt",
      outputContent: 'Form: F_OrderEntry\n  └─ triggers ClickEvent\n      └─ calls Q_GetOrder\n          └─ reads tblOrders (Col: CustName)'
    },
    {
      id: 2,
      layer: "Layer 3",
      title: "Excel Documentation",
      shortDesc: "Compiles technical specifications into review Excel sheets.",
      icon: FileSpreadsheet,
      link: "/layer3",
      color: "indigo",
      badgeColor: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20",
      glowColor: "rgba(99, 102, 241, 0.05)",
      details: "Compiles technical specifications and tables mapping into Excel sheets.",
      inputLabel: "vba_brain_mapping_logic.txt",
      inputType: "txt",
      inputContent: "• Screen Form specifications\n• Database layout relations\n• Logic rule extraction arrays",
      outputLabel: "generated_excel_specifications.log",
      outputType: "txt",
      outputContent: "📊 BD_Specification.xlsx (12 Tables)\n📊 DD_ScreenDefinition.xlsx (8 Forms)\n📊 DD_MacroModule.xlsx (35 Macros)"
    },
    {
      id: 3,
      layer: "Layer 4",
      title: "SQL Dialect Conversion",
      shortDesc: "Translates MS Access SQL formulas into standard enterprise SQL.",
      icon: Database,
      link: "/layer4",
      color: "indigo",
      badgeColor: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20",
      glowColor: "rgba(99, 102, 241, 0.05)",
      details: "Translates proprietary Access SQL function queries into enterprise server SQL dialect.",
      inputLabel: "ms_access_source.sql",
      inputType: "sql",
      inputContent: "SELECT OrderID, \n  IIf(Status='A', \n      'Active', 'Inactive') AS State\nFROM Orders;",
      outputLabel: "oracle_target_dialect.sql",
      outputType: "sql",
      outputContent: "SELECT OrderID,\n  CASE WHEN Status = 'A' \n       THEN 'Active'\n       ELSE 'Inactive' \n  END AS State\nFROM Orders;"
    },
    {
      id: 4,
      layer: "Layer 5",
      title: "C# & WPF Generation",
      shortDesc: "Compiles WPF view screens and clean C# MVVM backend logic.",
      icon: Cpu,
      link: "/layer5",
      color: "indigo",
      badgeColor: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20",
      glowColor: "rgba(99, 102, 241, 0.05)",
      details: "Compiles WPF XAML layouts and maps C# backend MVVM logic scripts.",
      inputLabel: "ModernWpfView.xaml",
      inputType: "xml",
      inputContent: '<TextBox Text="{Binding OrderNo}" />\n<Button Content="Process"\n  Command="{Binding ProcessCmd}" />',
      outputLabel: "ModernWpfViewModel.cs",
      outputType: "csharp",
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
    <div className="flex-1 w-full min-h-screen bg-neutral-50 dark:bg-[#030303] text-neutral-800 dark:text-neutral-250 font-sans selection:bg-indigo-500/30 selection:text-white relative overflow-x-hidden scroll-smooth transition-colors duration-300">
      
      {/* 1. Scroll Progress Bar */}
      <motion.div 
        className="fixed top-0 left-0 right-0 h-[3px] bg-indigo-650 dark:bg-indigo-550 origin-left z-50" 
        style={{ scaleX }} 
      />

      <style>{`
        .grid-mesh {
          background-image: radial-gradient(circle at 1px 1px, rgba(0, 0, 0, 0.02) 1px, transparent 0);
          background-size: 24px 24px;
        }
        .dark .grid-mesh {
          background-image: radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.015) 1px, transparent 0);
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
          background: linear-gradient(to bottom right, rgba(99, 102, 241, 0.25), transparent, rgba(148, 163, 184, 0.15));
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        .radar-scan-line {
          background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.15) 50%, transparent 100%);
          background-size: 100% 200px;
          animation: scanVertical 2.5s linear infinite;
        }

        .animate-marquee-left {
          display: flex;
          width: max-content;
          animation: marqueeScroll 35s linear infinite;
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
          <section className="w-full pt-20 sm:pt-28 pb-16 sm:pb-24 px-8 sm:px-16 md:px-20 flex justify-center border-b border-neutral-200 dark:border-neutral-900/85 relative">
            <motion.div 
              initial="hidden"
              animate="visible"
              variants={staggerContainerVariants}
              className="max-w-5xl w-full flex flex-col items-center text-center"
            >
              {/* Premium Heading */}
              <motion.h1 
                variants={fadeInUpVariants}
                className="text-4xl sm:text-6xl md:text-7xl lg:text-8xl font-extrabold tracking-tight text-neutral-900 dark:text-white mb-10 leading-tight pt-4"
              >
                Rebuild Legacy Access <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400">
                  in 5 Intelligent Layers
                </span>
              </motion.h1>
              
              {/* Subtitle */}
              <motion.p 
                variants={fadeInUpVariants}
                className="text-base sm:text-xl md:text-2xl text-neutral-655 dark:text-neutral-400 max-w-4xl mx-auto mb-20 font-normal leading-loose tracking-wide"
              >
                An advanced multi-agent AI pipeline translating legacy MS Access files into modern WPF C# client applications with compile-safe accuracy.
              </motion.p>
              
              {/* Action Buttons */}
              <motion.div 
                variants={fadeInUpVariants}
                className="flex flex-col sm:flex-row items-center justify-center gap-8 mb-28 w-full max-w-2xl mx-auto"
              >
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="w-full sm:w-auto">
                  <Link href="/layer1" className="w-full sm:w-auto inline-flex items-center justify-center gap-3 bg-indigo-650 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white font-semibold py-4 px-12 text-sm sm:text-base tracking-wider rounded-full shadow-md hover:shadow-indigo-500/20 transition-all duration-300 whitespace-nowrap">
                    <span>Get Started</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </motion.div>
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="w-full sm:w-auto">
                  <Link href="#timeline-tabs" className="w-full sm:w-auto inline-flex items-center justify-center bg-white dark:bg-white/5 text-neutral-800 dark:text-white font-semibold py-4 px-12 text-sm sm:text-base tracking-wider rounded-full border border-neutral-250 dark:border-white/10 hover:bg-neutral-100 dark:hover:bg-white/10 shadow-md transition-all duration-300 whitespace-nowrap">
                    Explore Architecture
                  </Link>
                </motion.div>
              </motion.div>

              {/* Live Transformation Bridge Layout */}
              <motion.div 
                variants={fadeInUpVariants}
                className="w-full max-w-5xl bg-white dark:bg-neutral-950/45 backdrop-blur-md border border-neutral-250 dark:border-neutral-900 rounded-3xl p-14 sm:p-20 relative overflow-hidden mb-20 shadow-md dark:shadow-2xl"
              >
                {/* Connecting Laser Line */}
                <div className="absolute top-1/2 left-[25%] right-[25%] h-[1px] bg-neutral-200 dark:bg-neutral-800 -translate-y-1/2 hidden md:block" />

                <div className="flex flex-col md:flex-row items-center justify-between gap-14 md:gap-20 relative z-10">
                  
                  {/* Left Side: Legacy Tech Stack */}
                  <motion.div 
                    whileHover={{ y: -5 }}
                    className="flex flex-col items-center gap-10 bg-neutral-50/50 dark:bg-neutral-900/30 border border-neutral-200 dark:border-neutral-850 p-10 rounded-2xl w-full md:w-[360px] shadow-sm transition-all duration-300"
                  >
                    <span className="text-[10px] font-bold text-neutral-550 dark:text-neutral-450 tracking-[0.2em] uppercase">Legacy Stack</span>
                    <div className="flex items-center gap-6 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-150 dark:border-indigo-900/30 shrink-0">
                        <DatabaseZap className="w-5 h-5 text-indigo-650 dark:text-indigo-400" />
                      </div>
                      <div className="text-left min-w-0">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white truncate">Access Database</div>
                        <div className="text-[11px] text-neutral-550 font-mono mt-0.5">.accdb / .mdb tables</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-150 dark:border-indigo-900/30 shrink-0">
                        <FileSpreadsheet className="w-5 h-5 text-indigo-650 dark:text-indigo-400" />
                      </div>
                      <div className="text-left min-w-0">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white truncate">VBA Screen Code</div>
                        <div className="text-[11px] text-neutral-550 font-mono mt-0.5">Macros & Functions</div>
                      </div>
                    </div>
                  </motion.div>

                  {/* Middle Node: AI core converter */}
                  <div className="relative flex flex-col items-center select-none shrink-0 py-6">
                    <motion.div 
                      whileHover={{ scale: 1.08 }}
                      className="w-24 h-24 rounded-full bg-indigo-650 dark:bg-indigo-555 flex items-center justify-center shadow-lg animate-pulse cursor-pointer"
                    >
                      <Bot className="w-10 h-10 text-white animate-bounce" />
                    </motion.div>
                    <div className="text-xs font-bold text-neutral-900 dark:text-white mt-4 tracking-wider uppercase">vba_brain AI Core</div>
                    <div className="text-[9px] text-indigo-600 dark:text-indigo-455 mt-1 font-mono uppercase">Pipeline Active</div>
                  </div>

                  {/* Right Side: Modern Target */}
                  <motion.div 
                    whileHover={{ y: -5 }}
                    className="flex flex-col items-center gap-10 bg-neutral-50/50 dark:bg-neutral-900/30 border border-neutral-200 dark:border-neutral-850 p-10 rounded-2xl w-full md:w-[360px] shadow-sm transition-all duration-300"
                  >
                    <span className="text-[10px] font-bold text-neutral-555 dark:text-neutral-400 tracking-[0.2em] uppercase">Modern Target</span>
                    <div className="flex items-center gap-6 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center border border-indigo-150 dark:border-indigo-900/30 shrink-0">
                        <Cpu className="w-5 h-5 text-indigo-650 dark:text-indigo-400" />
                      </div>
                      <div className="text-left min-w-0">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white truncate">Avalonia WPF Client</div>
                        <div className="text-[11px] text-neutral-555 font-mono mt-0.5">Modern C# & MVVM</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 w-full">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-[#090b10] flex items-center justify-center border border-indigo-150 dark:border-indigo-900/30 shrink-0">
                        <Database className="w-5 h-5 text-indigo-650 dark:text-indigo-400" />
                      </div>
                      <div className="text-left min-w-0">
                        <div className="text-sm font-bold text-neutral-900 dark:text-white truncate">Oracle SQL Server</div>
                        <div className="text-[11px] text-neutral-555 font-mono mt-0.5">Optimized Dialect</div>
                      </div>
                    </div>
                  </motion.div>

                </div>
              </motion.div>
            </motion.div>
          </section>

          {/* 2. Interactive Translation Playground */}
          <section id="playground" className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center border-b border-neutral-200 dark:border-neutral-900/80 bg-neutral-100/40 dark:bg-[#050506]/80 relative">
            <div className="max-w-5xl w-full flex flex-col items-center gap-20 sm:gap-24">
              
              {/* Header Title */}
              <motion.div 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-center max-w-3xl flex flex-col items-center"
              >
                <div className="inline-flex items-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-6">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Interactive Playground</span>
                </div>
                <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-neutral-900 dark:text-white tracking-wide mb-8 leading-tight">
                  Watch legacy VBA evolve into C# in real time
                </h2>
                <p className="text-neutral-600 dark:text-neutral-400 font-normal leading-loose text-base sm:text-lg max-w-2xl tracking-wide">
                  Deconstructs legacy Access databases into syntax trees and synthesizes modern C# EF Core backend code in real time.
                </p>
              </motion.div>

              {/* Code Editor View */}
              <motion.div 
                initial={{ opacity: 0, y: 40, scale: 0.98 }}
                whileInView={{ opacity: 1, y: 0, scale: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-5xl bg-[#090a0f] border border-neutral-250 dark:border-neutral-800 rounded-2xl overflow-hidden shadow-lg dark:shadow-2xl relative"
              >
                {/* Editor Top Bar */}
                <div className="flex items-center justify-between px-5 py-4 bg-[#0d0e15] border-b border-neutral-900/80 select-none">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                    <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                    <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                    <span className="text-[11px] font-mono text-neutral-500 ml-3">vba_brain_compiler_agent.py</span>
                  </div>
                  {isConverted && (
                    <motion.button 
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={handleResetConversion} 
                      className="text-xs text-neutral-350 hover:text-white bg-neutral-900 border border-neutral-800 hover:border-neutral-700 px-4 py-1.5 rounded-full transition-all cursor-pointer font-semibold"
                    >
                      Reset Demo
                    </motion.button>
                  )}
                </div>

                {/* Code Panel Split */}
                <div className="grid grid-cols-1 md:grid-cols-2 relative font-mono text-xs sm:text-sm">
                  
                  {/* Left: Source VBA */}
                  <div className="p-8 sm:p-10 bg-[#0b0c10] flex flex-col border-b md:border-b-0 md:border-r border-neutral-900">
                    <div className="flex items-center justify-between pb-3 border-b border-neutral-900/60 mb-6 select-none">
                      <span className="text-[10px] font-bold text-neutral-450 uppercase tracking-wider font-sans">VBA Source Code</span>
                      <span className="text-[9px] font-mono text-cyan-400/80 bg-cyan-500/5 px-2 py-0.5 rounded border border-cyan-500/10">vba_legacy</span>
                    </div>
                    <div className="flex font-mono text-xs sm:text-sm">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900/80 text-right select-none text-[10px] sm:text-xs leading-8">
                        {vbaCode.split('\n').map((_, idx) => (
                          <div key={idx} className="h-8">{idx + 1}</div>
                        ))}
                      </div>
                      <pre className="pl-4 text-cyan-455/95 overflow-x-auto flex-1 leading-8">
                        {highlightVBA(vbaCode)}
                      </pre>
                    </div>
                  </div>

                  {/* Right: Output C# */}
                  <div className="p-8 sm:p-10 bg-[#06070a] flex flex-col relative min-h-[380px]">
                    <div className="flex items-center justify-between pb-3 border-b border-neutral-900/60 mb-6 select-none">
                      <span className="text-[10px] font-bold text-neutral-455 uppercase tracking-wider font-sans">C# Target (EF Core)</span>
                      <span className="text-[9px] font-mono text-purple-400/80 bg-purple-400/5 px-2 py-0.5 rounded border border-purple-400/10">csharp_net8</span>
                    </div>
                    
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
                          <span className="text-neutral-500 font-sans text-xs">Awaiting compiler execution...</span>
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
                          <RefreshCw className="w-7 h-7 animate-spin text-indigo-400" />
                          <span className="text-[10px] tracking-wider uppercase font-bold text-neutral-400 font-sans">{statusText}</span>
                          <span className="text-lg font-bold text-white">{progress}%</span>
                        </motion.div>
                      )}

                      {isConverted && (
                        <motion.div 
                          key="result"
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.4 }}
                          className="flex font-mono text-xs sm:text-sm"
                        >
                          <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900/80 text-right select-none text-[10px] sm:text-xs leading-8">
                            {csharpCode.split('\n').map((_, idx) => (
                              <div key={idx} className="h-8">{idx + 1}</div>
                            ))}
                          </div>
                          <pre className="pl-4 text-purple-300/95 overflow-x-auto flex-1 leading-8">
                            {highlightCSharp(csharpCode)}
                          </pre>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Compilation Play Trigger Overlay */}
                {!isConverting && !isConverted && (
                  <div className="absolute inset-0 bg-neutral-950/45 dark:bg-neutral-950/65 backdrop-blur-[1.5px] flex items-center justify-center z-25 animate-fade-in">
                    <motion.button
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={handleStartConversion}
                      className="group flex items-center gap-2 bg-indigo-650 hover:bg-indigo-750 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white font-semibold text-xs sm:text-sm py-3 px-8 rounded-full shadow-lg transition-all duration-300 cursor-pointer tracking-wider uppercase whitespace-nowrap"
                    >
                      <Play className="w-4 h-4 text-white fill-white animate-pulse" />
                      <span>Execute Compiler Agent</span>
                    </motion.button>
                  </div>
                )}

              </motion.div>

            </div>
          </section>

          {/* 3. Infinite Logo / Feature Marquee */}
          <section className="w-full py-14 sm:py-16 bg-neutral-100 dark:bg-neutral-950 border-b border-neutral-200 dark:border-neutral-900 overflow-hidden relative select-none">
            <div className="animate-marquee-left flex gap-24 items-center">
              {[
                "Database Schemas Mapped", "VBA Form parsing", "WPF UI Generation", "SQL dialect conversion",
                "Domain-Driven Design (DDD)", "EF Core scaffolding", "Oracle / SQL Server scripts", "MVVM Architecture Patterns",
                "Database Schemas Mapped", "VBA Form parsing", "WPF UI Generation", "SQL dialect conversion",
                "Domain-Driven Design (DDD)", "EF Core scaffolding", "Oracle / SQL Server scripts", "MVVM Architecture Patterns"
              ].map((text, idx) => (
                <div key={idx} className="flex items-center gap-3.5 text-xs font-mono text-neutral-600 dark:text-neutral-400 uppercase tracking-widest whitespace-nowrap">
                  <Sparkles className="w-3 h-3 text-indigo-650 dark:text-indigo-400/50" />
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </section>

          {/* A. Step-by-Step Migration Journey (Vertical Scroll Timeline) */}
          <section className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center bg-white dark:bg-[#030303] border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              {/* Header */}
              <div className="text-center mb-24 max-w-2xl flex flex-col items-center">
                <div className="inline-flex items-center gap-2 text-indigo-650 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-6">
                  <Workflow className="w-4 h-4" />
                  <span>Migration Flow</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide mb-6 leading-tight">The 5-Step Migration Journey</h2>
                <p className="text-neutral-655 dark:text-neutral-400 text-base sm:text-lg leading-relaxed">
                  How vba_brain ingests, analyzes, compiles, and verifies your legacy databases automatically.
                </p>
              </div>

              {/* Vertical Timeline */}
              <div className="relative w-full flex flex-col gap-24 sm:gap-36 pl-14 sm:pl-24 border-l-2 border-neutral-200 dark:border-neutral-850">
                {[
                  {
                    step: "01",
                    title: "AST Source Extraction",
                    subtitle: "Ingestion and structural parsing",
                    desc: "Scans raw legacy tables, relationships, and VBA modules into a structured AST JSON representation.",
                    badge: "Layer 1: Parser"
                  },
                  {
                    step: "02",
                    title: "Dependency Graph Mapping",
                    subtitle: "Logic isolation and routing",
                    desc: "Maps database queries and VBA handlers to build a complete application dependency flow graph.",
                    badge: "Layer 2: Logic"
                  },
                  {
                    step: "03",
                    title: "Automated Specification Sheets",
                    subtitle: "Technical documentation compilation",
                    desc: "Generates standardized technical specification workbooks detailing form layouts and mappings.",
                    badge: "Layer 3: Specs"
                  },
                  {
                    step: "04",
                    title: "SQL Dialect Conversion",
                    subtitle: "Proprietary dialect rewrite",
                    desc: "Rewrites proprietary Access SQL queries into optimized PostgreSQL or Oracle server scripts.",
                    badge: "Layer 4: SQL"
                  },
                  {
                    step: "05",
                    title: "C# WPF MVVM Synthesis",
                    subtitle: "Modern client compilation",
                    desc: "Synthesizes modern WPF XAML views and compiles MVVM C# backend controller services.",
                    badge: "Layer 5: Build"
                  }
                ].map((item, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, x: -15 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5, delay: idx * 0.05 }}
                    className="relative group"
                  >
                    {/* Timeline circle dot indicator */}
                    <div className="absolute left-[-66px] sm:left-[-106px] top-2.5 w-5 h-5 rounded-full border-2 border-indigo-655 dark:border-indigo-500 bg-white dark:bg-[#030303] group-hover:bg-indigo-650 dark:group-hover:bg-indigo-500 transition-all duration-300 shadow-sm" />
                    
                    <div className="flex flex-col gap-4 sm:gap-5">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-[10px] font-mono font-bold text-indigo-650 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/45 px-2.5 py-1 rounded border border-indigo-100 dark:border-indigo-900/30">
                          {item.badge}
                        </span>
                        <span className="text-2xl font-black text-neutral-350 dark:text-neutral-800 font-mono tracking-tighter">{item.step}</span>
                      </div>
                      <h3 className="text-lg sm:text-xl font-bold text-neutral-900 dark:text-white mt-0.5 group-hover:text-indigo-650 dark:group-hover:text-indigo-400 transition-colors duration-300">
                        {item.title}
                      </h3>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                        {item.subtitle}
                      </h4>
                      <p className="text-sm sm:text-base text-neutral-600 dark:text-neutral-400 leading-loose max-w-2xl mt-1 font-normal">
                        {item.desc}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* 4. Interactive 5-Layer Workspace Tabs */}
          <section id="timeline-tabs" className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center relative border-b border-neutral-200 dark:border-neutral-900/80 bg-white dark:bg-[#030303]">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              {/* Header */}
              <motion.div 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-center mb-20 max-w-3xl"
              >
                <div className="inline-flex items-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-5">
                  <Layers className="w-4 h-4" />
                  <span>Pipeline Architecture</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide mb-6">Interactive 5-Layer Workflow</h2>
                <p className="text-neutral-655 dark:text-neutral-400 text-base sm:text-lg leading-relaxed font-normal">
                  Inspect how legacy components are extracted, mapped, and compiled through each phase of the migration pipeline.
                </p>
              </motion.div>

              {/* Tab Switcher */}
              <motion.div 
                initial={{ opacity: 0, y: 25 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-wrap items-center justify-center gap-6 w-full max-w-5xl mb-20 relative"
              >
                {layersInfo.map((l, idx) => {
                  const Icon = l.icon;
                  const isActive = activeLayerTab === idx;
                  return (
                    <button
                      key={idx}
                      onClick={() => setActiveLayerTab(idx)}
                      className={`flex-1 min-w-[140px] sm:min-w-[180px] max-w-[220px] flex flex-col items-center gap-4 p-5 sm:p-6 rounded-2xl border transition-all duration-300 cursor-pointer relative overflow-hidden group ${
                        isActive 
                           ? "border-transparent text-neutral-900 dark:text-white" 
                           : "border-neutral-200 dark:border-neutral-900/60 text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-950/40"
                      }`}
                    >
                      {/* Active Tab Pill */}
                      {isActive && (
                        <motion.div 
                          layoutId="activeLayerTabPill"
                          className="absolute inset-0 bg-neutral-100/80 dark:bg-neutral-900/60 border border-indigo-200 dark:border-indigo-500/40 rounded-2xl z-0"
                          transition={{ type: "spring", stiffness: 350, damping: 28 }}
                        />
                      )}
                      
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 relative z-10 ${
                        isActive ? "bg-indigo-100 dark:bg-indigo-500/10 text-indigo-650 dark:text-indigo-400 scale-105" : "bg-neutral-100 dark:bg-neutral-900 text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"
                      }`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <div className="flex flex-col items-center gap-1 relative z-10 text-center w-full min-w-0 overflow-hidden">
                        <span className="text-[9px] font-bold tracking-widest uppercase opacity-75">{l.layer}</span>
                        <span className="text-xs font-bold leading-snug mt-0.5 min-h-[1.5rem] flex items-center justify-center px-1 break-words w-full">
                          {l.title}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </motion.div>

              {/* Tab Content Box */}
              <motion.div 
                key={activeLayerTab}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="w-full bg-neutral-50 dark:bg-[#050506] border border-neutral-200 dark:border-neutral-850 rounded-3xl p-12 sm:p-16 shadow-md dark:shadow-2xl relative overflow-hidden flex flex-col gap-14"
              >
                {/* Subtle Glow Backdrop */}
                <div 
                  className="absolute -top-1/2 -left-1/2 w-full h-full rounded-full blur-[120px] pointer-events-none transition-all duration-750 opacity-40 dark:opacity-100"
                  style={{ background: layersInfo[activeLayerTab].glowColor }}
                />

                {/* Top Section */}
                <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-10 border-b border-neutral-200 dark:border-neutral-900 pb-10">
                  <div className="flex flex-col gap-3">
                    <span className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold border w-fit ${layersInfo[activeLayerTab].badgeColor}`}>
                      <Sparkles className="w-3.5 h-3.5" />
                      {layersInfo[activeLayerTab].layer} Active
                    </span>
                    <h3 className="text-2xl sm:text-3xl font-bold tracking-wide text-neutral-900 dark:text-white leading-snug">{layersInfo[activeLayerTab].title}</h3>
                  </div>
                  <div className="max-w-xl">
                    <p className="text-neutral-650 dark:text-neutral-450 text-base sm:text-lg leading-relaxed font-normal">
                      {layersInfo[activeLayerTab].details}
                    </p>
                  </div>
                </div>

                {/* Bottom Section (Mock IDE Grid) */}
                <div className="relative z-10 w-full grid grid-cols-1 md:grid-cols-2 gap-8">
                  {/* Input Mock Editor */}
                  <div className="flex flex-col rounded-xl border border-neutral-250 dark:border-neutral-900 bg-[#07080b]/95 shadow-md dark:shadow-2xl min-w-0 overflow-hidden">
                    {/* IDE Header */}
                    <div className="flex items-center justify-between px-5 py-3.5 bg-[#0d0e12] border-b border-neutral-900/80 select-none">
                      <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider font-sans">{layersInfo[activeLayerTab].inputLabel}</span>
                      <span className="text-[9px] font-mono text-neutral-500 uppercase bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">{layersInfo[activeLayerTab].inputType}</span>
                    </div>
                    {/* IDE Body */}
                    <div className="flex p-6 sm:p-8 font-mono text-xs sm:text-sm leading-7 overflow-x-auto">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900 text-right select-none text-[10px] sm:text-xs leading-7">
                        {layersInfo[activeLayerTab].inputContent.split('\n').map((_, idx) => (
                          <div key={idx} className="h-7">{idx + 1}</div>
                        ))}
                      </div>
                      <pre className="pl-4 text-neutral-350 overflow-x-auto flex-1 w-full leading-7">
                        {highlightCode(layersInfo[activeLayerTab].inputContent, layersInfo[activeLayerTab].inputType)}
                      </pre>
                    </div>
                  </div>

                  {/* Output Mock Editor */}
                  <div className="flex flex-col rounded-xl border border-neutral-250 dark:border-neutral-900 bg-[#07080b]/95 shadow-md dark:shadow-2xl min-w-0 overflow-hidden">
                    {/* IDE Header */}
                    <div className="flex items-center justify-between px-5 py-3.5 bg-[#0d0e12] border-b border-neutral-900/80 select-none">
                      <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider font-sans">{layersInfo[activeLayerTab].outputLabel}</span>
                      <span className="text-[9px] font-mono text-indigo-455 uppercase bg-indigo-500/5 px-2 py-0.5 rounded border border-indigo-500/10">{layersInfo[activeLayerTab].outputType}</span>
                    </div>
                    {/* IDE Body */}
                    <div className="flex p-6 sm:p-8 font-mono text-xs sm:text-sm leading-7 overflow-x-auto">
                      <div className="flex flex-col text-neutral-600 pr-4 border-r border-neutral-900 text-right select-none text-[10px] sm:text-xs leading-7">
                        {layersInfo[activeLayerTab].outputContent.split('\n').map((_, idx) => (
                          <div key={idx} className="h-7">{idx + 1}</div>
                        ))}
                      </div>
                      <pre className="pl-4 text-indigo-300/95 overflow-x-auto flex-1 w-full leading-7">
                        {highlightCode(layersInfo[activeLayerTab].outputContent, layersInfo[activeLayerTab].outputType)}
                      </pre>
                    </div>
                  </div>
                </div>

                {/* Workspace action link */}
                <div className="relative z-10 flex justify-end">
                  <Link 
                    href={layersInfo[activeLayerTab].link} 
                    className="inline-flex items-center gap-1 text-xs sm:text-sm font-bold text-indigo-650 dark:text-indigo-400 hover:text-indigo-750 dark:hover:text-indigo-300 group tracking-wide transition-colors"
                  >
                    <span>Open {layersInfo[activeLayerTab].layer} Workspace</span>
                    <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform duration-300" />
                  </Link>
                </div>
              </motion.div>

            </div>
          </section>

          {/* B. Capabilities Metrics Dashboard */}
          <section className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center bg-[#fafafa] dark:bg-[#050506]/70 border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              {/* Header */}
              <div className="text-center mb-24 max-w-2xl mx-auto">
                <div className="inline-flex items-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-6">
                  <Monitor className="w-4 h-4" />
                  <span>Pipeline Scale</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide">Enterprise Scaling Metrics</h2>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 sm:gap-14 w-full">
                {[
                  { value: "99.8%", label: "Accuracy Rate", desc: "Automated syntax compilation correctness" },
                  { value: "10x", label: "Migration Speed", desc: "Faster delivery compared to manual engineering" },
                  { value: "500k+", label: "Lines of Code", desc: "Supported database parsing capacity" },
                  { value: "Zero", label: "Data Leak Risk", desc: "Completely offline parsing rules" }
                ].map((metric, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, y: 15 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: idx * 0.05 }}
                    className="flex flex-col p-8 sm:p-10 lg:p-12 bg-white dark:bg-[#090a0f] border border-neutral-250 dark:border-neutral-850 rounded-3xl shadow-sm text-center gap-6 hover:shadow-md transition-shadow duration-300"
                  >
                    <span className="text-4xl sm:text-5xl md:text-6xl font-black text-indigo-650 dark:text-indigo-400 tracking-tight">{metric.value}</span>
                    <span className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white">{metric.label}</span>
                    <span className="text-sm sm:text-base text-neutral-500 dark:text-neutral-400 font-normal leading-loose">{metric.desc}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* C. Manual Rewrite vs. vba_brain Comparison Table */}
          <section className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center bg-white dark:bg-[#030303] border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              {/* Header */}
              <div className="text-center mb-24 max-w-2xl mx-auto">
                <div className="inline-flex items-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-6">
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Strategic Advantage</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide mb-5">Manual Rewrite vs. vba_brain</h2>
                <p className="text-neutral-650 dark:text-neutral-450 text-base sm:text-lg font-normal">
                  A side-by-side structural comparison of development workflows.
                </p>
              </div>

              {/* Table wrapper */}
              <div className="w-full overflow-x-auto rounded-3xl border border-neutral-200 dark:border-neutral-850 shadow-sm mt-10">
                <table className="w-full text-left border-collapse text-sm sm:text-base font-sans min-w-[650px]">
                  <thead>
                    <tr className="bg-neutral-100/50 dark:bg-neutral-900/40 border-b border-neutral-200 dark:border-neutral-850">
                      <th className="py-6 px-6 sm:py-8 sm:px-10 font-bold text-neutral-900 dark:text-white">Feature Metric</th>
                      <th className="py-6 px-6 sm:py-8 sm:px-10 font-bold text-neutral-600 dark:text-neutral-400">Manual Engineering</th>
                      <th className="py-6 px-6 sm:py-8 sm:px-10 font-bold text-indigo-650 dark:text-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/10">vba_brain Pipeline</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { metric: "Migration Speed", manual: "Weeks to months per screen", auto: "Seconds per module" },
                      { metric: "Syntax Accuracy", manual: "Frequent human logic errors", auto: "99.8% AST mapping precision" },
                      { metric: "Documentation", manual: "Sparsely updated markdown logs", auto: "Auto-seeded technical Excel sheets" },
                      { metric: "Architecture Design", manual: "Variable pattern consistency", auto: "Strict DDD / Clean MVVM WPF target" },
                      { metric: "Dialect Validation", manual: "Manual SQL function checking", auto: "Real-time dialect compiler scripts" }
                    ].map((row, idx) => (
                      <tr key={idx} className="border-b border-neutral-200 dark:border-neutral-850 last:border-0 hover:bg-neutral-50/50 dark:hover:bg-neutral-900/10 transition-colors">
                        <td className="py-6 px-6 sm:py-8 sm:px-10 font-bold text-neutral-900 dark:text-white">{row.metric}</td>
                        <td className="py-6 px-6 sm:py-8 sm:px-10 text-neutral-500 dark:text-neutral-500 font-normal">{row.manual}</td>
                        <td className="py-6 px-6 sm:py-8 sm:px-10 text-indigo-750 dark:text-indigo-355 bg-indigo-50/10 dark:bg-indigo-950/5 font-semibold">{row.auto}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* 5. Technology Stack & Rules Section */}
          <section id="features" className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center bg-neutral-50 dark:bg-[#030303] border-b border-neutral-200 dark:border-neutral-900/80">
            <div className="max-w-5xl w-full flex flex-col items-center">
              
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="text-center mb-24 max-w-2xl mx-auto"
              >
                <div className="inline-flex items-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase mb-6">
                  <Code2 className="w-4 h-4" />
                  <span>Scaffold Architecture</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide mb-6">Designed for Clean Code Standards</h2>
                <p className="text-neutral-655 dark:text-neutral-455 text-base sm:text-lg leading-relaxed font-normal">
                  Outputs modular, testable C# architectures structured for high enterprise standards.
                </p>
              </motion.div>

              {/* Rules Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-10 sm:gap-14 w-full">
                {[
                  { 
                    title: "Domain Driven Design (DDD)", 
                    desc: "Splits C# target projects into Domain, Application, UI, and Infrastructure layers.",
                    icon: (
                      <svg className="w-8 h-8 text-indigo-655 dark:text-indigo-400 mb-8 group-hover:scale-105 transition-transform duration-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M12 2L2 7l10 5 10-5-10-5z" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M2 17l10 5 10-5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )
                  },
                  { 
                    title: "Clean MVVM Separation", 
                    desc: "Removes hardcoded event code-behind files, binding layouts to reactive properties.",
                    icon: (
                      <svg className="w-8 h-8 text-indigo-655 dark:text-indigo-400 mb-8 group-hover:scale-105 transition-transform duration-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <rect x="2" y="3" width="20" height="14" rx="2" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M8 21h8" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M12 17v4" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M17 8l-3-3-3 3" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M7 12l3 3 3-3" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )
                  },
                  { 
                    title: "Secure Config Files", 
                    desc: "Ignores sensitive API credentials, keys, and connection strings automatically.",
                    icon: (
                      <svg className="w-8 h-8 text-indigo-655 dark:text-indigo-400 mb-8 group-hover:scale-105 transition-transform duration-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeLinecap="round" strokeLinejoin="round"/>
                        <circle cx="12" cy="11" r="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M12 12.5V15" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )
                  }
                ].map((item, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.7, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
                    className="bg-white dark:bg-neutral-950 border border-neutral-250 dark:border-neutral-900 rounded-3xl p-8 sm:p-10 lg:p-12 hover:shadow-md dark:hover:shadow-[0_20px_50px_rgba(99,102,241,0.05)] hover:border-indigo-455 dark:hover:border-indigo-500/30 transition-all duration-300 cursor-pointer relative group overflow-hidden"
                  >
                    <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-[30px] opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                    <div className="relative z-10">
                      {item.icon}
                      <div className="text-xl font-bold tracking-wide text-neutral-900 dark:text-white mb-5 group-hover:text-indigo-650 dark:group-hover:text-indigo-300 transition-colors duration-350">{item.title}</div>
                      <p className="text-base sm:text-lg text-neutral-550 dark:text-neutral-400 font-normal leading-loose">{item.desc}</p>
                    </div>
                  </motion.div>
                ))}
              </div>

            </div>
          </section>

          {/* 6. Live Activity Console */}
          <section className="w-full py-20 sm:py-28 px-8 sm:px-16 md:px-20 flex justify-center bg-neutral-100/30 dark:bg-[#050506]/90 border-b border-neutral-200 dark:border-neutral-900/80 relative">
            <div className="max-w-5xl w-full flex flex-col gap-20 sm:gap-24">
              
              {/* Header */}
              <div className="flex flex-col gap-4 text-center max-w-2xl mx-auto">
                <motion.div 
                  initial={{ opacity: 0, y: 15 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  className="inline-flex items-center justify-center gap-2 text-indigo-655 dark:text-indigo-400 text-xs font-bold tracking-wider uppercase"
                >
                  <Terminal className="w-4 h-4" />
                  <span>Live migration activity console</span>
                </motion.div>
                <motion.h2 
                  initial={{ opacity: 0, y: 15 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-wide"
                >
                  Real-time pipeline monitoring status
                </motion.h2>
              </div>
              
              <motion.div 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="bg-[#090a0f] border border-neutral-250 dark:border-neutral-805 p-12 sm:p-16 rounded-3xl font-mono text-xs md:text-sm text-neutral-300 leading-loose shadow-md dark:shadow-2xl flex flex-col gap-10 min-h-[380px]"
              >
                <div className="flex items-center justify-between border-b border-neutral-900/80 pb-5 mb-5 select-none">
                  <span className="text-[11px] text-neutral-500 font-bold uppercase tracking-wider">vba_brain_orchestrator.log</span>
                  <div className="flex items-center gap-2 text-[10px] text-emerald-655 dark:text-emerald-400 bg-emerald-55/10 dark:bg-emerald-500/10 border border-emerald-250 dark:border-emerald-500/20 px-3 py-1.5 rounded-full font-sans font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400 animate-ping"></span>
                    <span>Live Listener Active</span>
                  </div>
                </div>
                <div className="flex-1 flex flex-col gap-5 sm:gap-6 overflow-y-auto pr-2">
                  <AnimatePresence>
                    {logLines.map((line, idx) => (
                      <motion.div 
                        key={line + idx}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3 }}
                      >
                        {renderLogLine(line)}
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  <div className="flex items-center gap-1 mt-1 select-none">
                    <span className="text-indigo-400 mr-2.5 select-none font-mono">&gt;</span>
                    <span className="terminal-cursor"></span>
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
