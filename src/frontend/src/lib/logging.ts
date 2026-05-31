// Shared logging types & helpers for Layer 1–5 workspace consoles.

export type LogLevel = "INFO" | "WARN" | "ERROR" | "SUCCESS" | "RUNNING";

export interface LogEntry {
  time: string;
  level: LogLevel | string;
  message: string;
  agent?: string;
}

/** Locale timestamp used by every pipeline log line (24h, vi-VN). */
export function formatLogTime(date: Date = new Date()): string {
  return date.toLocaleTimeString("vi-VN", { hour12: false });
}

/** Map a log level to its themed CSS color token. */
export function getLogColor(level: string): string {
  switch (level) {
    case "ERROR":
      return "var(--danger)";
    case "SUCCESS":
      return "var(--success)";
    case "WARN":
      return "var(--warning)";
    default:
      return "var(--info)";
  }
}
