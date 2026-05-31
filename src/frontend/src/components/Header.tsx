"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  DatabaseZap, Bot, FileSpreadsheet, Database, Cpu, Sparkles, Sun, Moon 
} from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") || "dark";
    setTheme(savedTheme);
    if (savedTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "dark" ? "light" : "dark";
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    document.documentElement.style.colorScheme = newTheme;
    if (newTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  const tabs = [
    { href: "/layer1", label: "L1 Parser", icon: DatabaseZap, color: "#6366f1" },
    { href: "/layer2", label: "L2 Workflow", icon: Bot, color: "#8b5cf6" },
    { href: "/layer3", label: "L3 SQL", icon: Database, color: "#0ea5e9" },
    { href: "/layer4", label: "L4 Specs", icon: FileSpreadsheet, color: "#10b981" },
    { href: "/layer5", label: "L5 Agents", icon: Cpu, color: "#d946ef" },
  ];

  const isHomePage = pathname === "/";

  return (
    <header className={`flex items-center justify-between px-6 relative w-full select-none transition-all duration-300 ${
      isHomePage 
        ? "h-[60px] bg-transparent border-b-0 shadow-none" 
        : "layout-header"
    }`}>
      <div className="flex items-center gap-5">
        <Link href="/" className="flex items-center gap-4 cursor-pointer group no-underline">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-105 group-hover:shadow-indigo-500/50 transition-all duration-300">
            <span className="absolute inset-0 rounded-xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 blur-md opacity-40 group-hover:opacity-70 transition-opacity duration-300" />
            <Sparkles className="w-4 h-4 text-white relative z-10" />
          </div>
          <span className="font-extrabold text-lg tracking-tight text-neutral-900 dark:text-white/95">
            vba_brain{!isHomePage && <span className="text-indigo-600 dark:text-indigo-400 text-base tracking-[0.15em] uppercase ml-1 opacity-80 font-semibold hidden sm:inline">Studio</span>}
          </span>
        </Link>
      </div>
      
      {!isHomePage ? (
        <div className="header-tabs bg-neutral-100 dark:bg-neutral-950/80 border border-neutral-200 dark:border-neutral-900">
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
                  color: isActive ? "#fff" : (theme === "dark" ? "#94a3b8" : "#4b5563"),
                  background: isActive
                    ? `linear-gradient(135deg, ${tab.color} 0%, ${tab.color}cc 100%)`
                    : "transparent",
                  boxShadow: isActive ? `0 2px 10px ${tab.color}66` : "none",
                  border: "1px solid transparent",
                }}
              >
                <Icon size={14} style={{ color: isActive ? "#fff" : tab.color, opacity: isActive ? 1 : 0.75 }} />
                <span className="tab-label hidden md:inline">{tab.label}</span>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className="flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 items-center justify-center pointer-events-none">
          <span className="text-[8px] sm:text-base md:text-base font-semibold tracking-wider text-neutral-500 dark:text-neutral-400 bg-neutral-200/40 dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800/80 px-2.5 py-1 sm:px-4 sm:py-1.5 rounded-full uppercase select-none pointer-events-auto whitespace-nowrap">
            <span className="inline sm:hidden">VBA to C#</span>
            <span className="hidden sm:inline">Next-Gen VBA to C# Scaffold Migration</span>
          </span>
        </div>
      )}

      <div className="flex items-center gap-4">
        <button 
          onClick={toggleTheme} 
          className="w-9 h-9 rounded-full flex items-center justify-center border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-[#0c0d12] text-neutral-600 dark:text-neutral-300 hover:border-indigo-400 dark:hover:border-indigo-500/60 hover:text-indigo-600 dark:hover:text-indigo-400 hover:rotate-12 transition-all duration-300 cursor-pointer shrink-0"
          aria-label="Toggle Theme"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
}
