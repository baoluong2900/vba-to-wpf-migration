"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Clock } from "lucide-react";

export default function Footer() {
  const pathname = usePathname();
  const isWorkspace = pathname?.startsWith("/layer");
  const [now, setNow] = useState<string>("");

  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString("vi-VN", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  if (isWorkspace) {
    return (
      <footer className="h-8 px-5 flex items-center justify-between border-t border-neutral-200 dark:border-white/5 bg-neutral-50 dark:bg-[#0b0c10] text-neutral-500 dark:text-gray-500 text-[11px] shrink-0 select-none">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75 animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <span className="font-semibold tracking-wider uppercase text-neutral-600 dark:text-gray-400">vba_brain Engine Active</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 font-mono tabular-nums text-neutral-600 dark:text-gray-400">
            <Clock size={12} className="text-indigo-500 dark:text-indigo-400" />
            <span suppressHydrationWarning>{now || "--:--:--"}</span>
          </span>
          <span className="hidden sm:inline font-light">© 2026 <span className="ws-gradient-text font-semibold">vba_brain</span> Studio</span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="py-8 text-center border-t border-neutral-200 dark:border-white/5 bg-neutral-50 dark:bg-[#050506] relative z-10 shrink-0">
      <p className="text-neutral-500 dark:text-gray-500 text-sm font-light">© 2026 <span className="ws-gradient-text font-semibold">vba_brain</span>. Elevating Legacy Systems.</p>
    </footer>
  );
}
