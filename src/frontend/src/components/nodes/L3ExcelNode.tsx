"use client";
import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Play, Loader2, CheckCircle, AlertCircle, Clock, Download, FileSpreadsheet } from "lucide-react";

const STATUS_CFG: Record<string, { color: string; bg: string; text: string; Icon: any }> = {
  idle:    { color: "var(--text-muted)", bg: "rgba(107,114,128,0.15)", text: "Idle",     Icon: Clock },
  running: { color: "#3b82f6", bg: "rgba(59,130,246,0.15)", text: "Running…", Icon: Loader2 },
  success: { color: "#10b981", bg: "rgba(16,185,129,0.15)", text: "Done",     Icon: CheckCircle },
  error:   { color: "#ef4444", bg: "rgba(239,68,68,0.15)", text: "Error",     Icon: AlertCircle },
};

function L3ExcelNodeInner({ data }: { data: any }) {
  const {
    nodeKey, label, icon, color, description,
    status, outputFile, outputSizeKb, errorMsg, duration,
    onGenerate, onDownload,
    selectedInput, hasData,
  } = data;

  const st = STATUS_CFG[status] || STATUS_CFG.idle;
  const StIcon = st.Icon;
  const isRunning = status === "running";

  return (
    <div style={{
      background: "var(--node-bg)",
      borderRadius: 12,
      width: 280,
      border: `1px solid ${status === "success" ? color : status === "running" ? "var(--brand-primary)" : "var(--border-color)"}`,
      boxShadow: isRunning ? `0 0 24px ${color}33` : "0 4px 16px rgba(0,0,0,0.25)",
      transition: "all 0.3s",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        gap: 8,
        borderBottom: "1px solid var(--border-color)",
        borderTop: `2px solid ${color}`,
        background: `linear-gradient(90deg, ${color}18, transparent)`,
      }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-main)" }}>{label}</div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{description}</div>
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 3,
          fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
          color: st.color, background: st.bg,
        }}>
          <StIcon size={10} style={isRunning ? { animation: "spin 1s linear infinite" } : {}} />
          {st.text}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: "8px 14px 12px", display: "flex", flexDirection: "column", gap: 6 }}>

        {/* Selected item badge */}
        {selectedInput && (
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            background: `${color}18`, border: `1px solid ${color}33`,
            borderRadius: 4, padding: "4px 8px",
          }}>
            <span style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, flexShrink: 0 }}>
              🖥️ Item:
            </span>
            <span style={{
              fontSize: 9, color: color, fontWeight: 600,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 180,
            }} title={selectedInput}>
              {selectedInput}
            </span>
          </div>
        )}

        {/* Data availability badge */}
        {selectedInput && (
          <div style={{ fontSize: 10, color: hasData ? "#6ee7b7" : "#f87171" }}>
            {hasData ? "✅ JSON có trong MongoDB" : "⚠️ Chưa có JSON (chạy BD/DD agent trước)"}
          </div>
        )}

        {/* Output file result */}
        {status === "success" && outputFile && (
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)",
            borderRadius: 4, padding: "4px 8px",
          }}>
            <FileSpreadsheet size={12} color="#10b981" />
            <span style={{ fontSize: 10, color: "#6ee7b7", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={outputFile}>
              {outputFile}
            </span>
            {outputSizeKb && (
              <span style={{ fontSize: 9, color: "var(--text-muted)", flexShrink: 0 }}>
                {outputSizeKb} KB
              </span>
            )}
          </div>
        )}

        {/* Duration */}
        {status === "success" && duration && (
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
            ⏱ {(duration / 1000).toFixed(1)}s
          </div>
        )}

        {/* Error */}
        {status === "error" && errorMsg && (
          <div style={{
            fontSize: 10, color: "#ef4444",
            background: "rgba(239,68,68,0.08)", padding: "4px 8px",
            borderRadius: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }} title={errorMsg}>
            ❌ {errorMsg}
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
          <button
            onClick={(e) => { e.stopPropagation(); onGenerate?.(); }}
            disabled={!selectedInput || isRunning}
            style={{
              flex: 1,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
              padding: "7px 8px", borderRadius: 6, border: "none",
              fontSize: 11, fontWeight: 600, cursor: selectedInput && !isRunning ? "pointer" : "not-allowed",
              background: selectedInput ? `linear-gradient(135deg, ${color}, ${color}cc)` : "var(--border-color)",
              color: selectedInput ? "#fff" : "var(--text-muted)",
              opacity: isRunning ? 0.7 : 1,
            }}
          >
            {isRunning
              ? <><Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> Generating…</>
              : <><Play size={11} /> Generate</>
            }
          </button>

          <button
            onClick={(e) => { e.stopPropagation(); onDownload?.(); }}
            disabled={status !== "success" || !outputFile}
            title={status === "success" ? "Download Excel file" : "Generate first"}
            style={{
              padding: "7px 10px", borderRadius: 6,
              border: `1px solid ${status === "success" ? color : "var(--border-color)"}`,
              background: status === "success" ? `${color}22` : "transparent",
              color: status === "success" ? color : "var(--text-muted)",
              cursor: status === "success" ? "pointer" : "not-allowed",
              display: "flex", alignItems: "center",
            }}
          >
            <Download size={13} />
          </button>
        </div>
      </div>

      {/* ReactFlow handles */}
      <Handle type="target" position={Position.Left} id="left"   style={{ background: color, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} id="right"  style={{ background: color, width: 8, height: 8 }} />
      <Handle type="target" position={Position.Top}  id="top"    style={{ background: color, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ background: color, width: 8, height: 8 }} />
    </div>
  );
}

export const L3ExcelNode = memo(L3ExcelNodeInner);
