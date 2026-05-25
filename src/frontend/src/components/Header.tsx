"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, Sparkles 
} from "lucide-react";

export default function Header() {
  const pathname = usePathname();

  const tabs = [
    { href: "/layer1", label: "L1 Parser", icon: DatabaseZap, color: "#22d3ee" },
    { href: "/layer2", label: "L2 Workflow", icon: Bot, color: "#c084fc" },
    { href: "/layer3", label: "L3 Excel", icon: FileSpreadsheet, color: "#34d399" },
    { href: "/layer4", label: "L4 SQL", icon: Database, color: "#fbbf24" },
    { href: "/layer5", label: "L5 Agents", icon: Cpu, color: "#fb7185" },
  ];

  return (
    <header className="layout-header flex items-center justify-between px-6 relative w-full select-none">
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-2 cursor-pointer group no-underline">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.3)] group-hover:shadow-[0_0_25px_rgba(168,85,247,0.5)] transition-all duration-500 group-hover:scale-105">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-extrabold text-lg tracking-tight text-white/95">
            vba_brain <span className="text-purple-400 text-xs tracking-[0.15em] uppercase ml-1 opacity-80 font-semibold hidden sm:inline">Studio</span>
          </span>
        </Link>
      </div>
      
      <div className="header-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`header-tab ${isActive ? "active" : ""}`}
              style={{
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                borderRadius: "7px",
                color: isActive ? "#fff" : "#94a3b8",
                background: isActive ? "rgba(255, 255, 255, 0.08)" : "transparent",
                boxShadow: isActive ? "0 1px 3px rgba(0,0,0,0.2)" : "none",
                border: "1px solid transparent",
              }}
            >
              <Icon size={14} style={{ color: tab.color, opacity: isActive ? 1 : 0.6 }} />
              <span className="tab-label hidden md:inline">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
}
