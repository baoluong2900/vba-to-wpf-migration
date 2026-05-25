"use client";

import { usePathname } from "next/navigation";

export default function Footer() {
  const pathname = usePathname();
  const isWorkspace = pathname?.startsWith("/layer");

  if (isWorkspace) {
    return (
      <footer className="h-8 px-6 flex items-center justify-between border-t border-white/5 bg-[#0b0c10] text-gray-500 text-xs shrink-0 select-none">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium text-[10px] tracking-wider uppercase text-gray-400">vba_brain Engine Active</span>
        </div>
        <p className="font-light text-[10px]">© 2026 vba_brain Migration Studio</p>
      </footer>
    );
  }

  return (
    <footer className="py-10 text-center border-t border-white/5 bg-[#050506] relative z-10 shrink-0">
      <p className="text-gray-500 text-sm font-light">© 2026 vba_brain Migration Studio. Elevating Legacy Systems.</p>
    </footer>
  );
}
