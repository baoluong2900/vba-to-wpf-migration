"use client";

import { usePathname } from "next/navigation";

export default function Footer() {
  const pathname = usePathname();
  const isWorkspace = pathname?.startsWith("/layer");

  if (isWorkspace) {
    return (
      <footer className="h-8 px-6 flex items-center justify-between border-t border-neutral-200 dark:border-white/5 bg-neutral-50 dark:bg-[#0b0c10] text-neutral-500 dark:text-gray-500 text-base shrink-0 select-none">
        <div className="flex items-center gap-4">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium text-base tracking-wider uppercase text-neutral-600 dark:text-gray-400">vba_brain Engine Active</span>
        </div>
        <p className="font-light text-base">© 2026 vba_brain Migration Studio</p>
      </footer>
    );
  }

  return (
    <footer className="py-8 text-center border-t border-neutral-200 dark:border-white/5 bg-neutral-50 dark:bg-[#050506] relative z-10 shrink-0">
      <p className="text-neutral-500 dark:text-gray-500 text-base sm:text-base font-light">© 2026 vba_brain. Elevating Legacy Systems.</p>
    </footer>
  );
}
