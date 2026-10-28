"use client";
import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Play, Loader2, CheckCircle, AlertCircle, Clock, Eye, FileCode2 } from "lucide-react";

const STATUS_CFG: Record<string, { color: string; bg: string; text: string; Icon: any }> = {
  idle:    { color: "var(--text-muted)", bg: "rgba(107,114,128,0.15)", text: "Idle", Icon: Clock },
  running: { color: "#3b82f6", bg: "rgba(59,130,246,0.15)", text: "Running...", Icon: Loader2 },
  success: { color: "#10b981", bg: "rgba(16,185,129,0.15)", text: "Done", Icon: CheckCircle },
  error:   { color: "#ef4444", bg: "rgba(239,68,68,0.15)", text: "Error", Icon: AlertCircle },
};

function L5AgentNodeInner({ data }: { data: any }) {
  const {
    agentKey, label, icon, color, description, inputs, outputs, status, files, duration, errorMsg,
    onRun, onViewInput, onViewOutput, isRunnable, selectedInput, inputLabel, currentModel, modelList, onModelChange,
  } = data;
  const st = STATUS_CFG[status] || STATUS_CFG.idle;
  const StIcon = st.Icon;
  const isRunning = status === "running";

  // Short model label for display
  const shortModel = (id: string) => {
    if (id.includes("coder-plus")) return "coder-plus";
    if (id.includes("480b")) return "coder-480b";
    if (id.includes("coder-next")) return "coder-next";
    if (id.includes("235b")) return "235b";
    return id.replace(/^qwen3-/, "").slice(0, 18);
  };

  return (
    <div style={{
      background: "var(--node-bg)", borderRadius: 12, width: 270,
      border: `1px solid ${status === "success" ? color : status === "running" ? "var(--brand-primary)" : "var(--border-color)"}`,
      boxShadow: isRunning ? `0 0 24px ${color}33` : "0 4px 16px rgba(0,0,0,0.25)",
      transition: "all 0.3s", overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "10px 14px", display: "flex", alignItems: "center", gap: 8,
        borderBottom: "1px solid var(--border-color)", borderTop: `2px solid ${color}`,
        background: `linear-gradient(90deg, ${color}18, transparent)`,
      }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-main)" }}>{label}</div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{description}</div>
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 3, fontSize: 10,
          fontWeight: 600, padding: "2px 6px", borderRadius: 4, color: st.color, background: st.bg,
        }}>
          <StIcon size={10} style={isRunning ? { animation: "spin 1s linear infinite" } : {}} /> {st.text}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: "8px 14px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
        {/* Model selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, whiteSpace: "nowrap" }}>🧠</span>
          <select
            value={currentModel || ""}
            onChange={(e) => { e.stopPropagation(); onModelChange?.(e.target.value); }}
            onClick={(e) => e.stopPropagation()}
            style={{
              flex: 1, background: "var(--bg-dark)", border: `1px solid var(--border-color)`,
              color: "var(--text-main)", borderRadius: 4, padding: "3px 4px", fontSize: 10, fontWeight: 600,
              outline: "none", cursor: "pointer",
            }}>
            {modelList && modelList.length > 0 ? (
              modelList.map((m: any) => <option key={m.id} value={m.id}>{m.id}</option>)
            ) : (
              <option value={currentModel}>{shortModel(currentModel || "default")}</option>
            )}
          </select>
        </div>

        {/* Selected input badge — all agents including mapping show readonly badge */}
        {selectedInput && (
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            background: `${color}18`, border: `1px solid ${color}33`,
            borderRadius: 4, padding: "4px 8px",
          }}>
            <span style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, flexShrink: 0 }}>
              {agentKey === "mapping" ? "🗺️" : inputLabel === "Query" ? "🗃️" : inputLabel === "Macro" ? "🔮" : inputLabel === "Module" ? "📦" : "🖥️"} {inputLabel}:
            </span>
            <span style={{
              fontSize: 9, color: color, fontWeight: 600,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160,
            }} title={selectedInput}>
              {selectedInput}
            </span>
          </div>
        )}

        {/* IO */}
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, marginBottom: 2 }}>IN</div>
            {(inputs || []).map((inp: string, i: number) => (
              <div key={i} style={{ fontSize: 10, color: "var(--text-muted)" }}><span style={{ color: "#3b82f6" }}>→</span> {inp}</div>
            ))}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, marginBottom: 2 }}>OUT</div>
            {(outputs || []).map((out: string, i: number) => (
              <div key={i} style={{ fontSize: 10, color: "var(--text-muted)" }}><span style={{ color: "#10b981" }}>←</span> {out}</div>
            ))}
          </div>
        </div>

        {/* Result info */}
        {files && files.length > 0 && (
          <div style={{ fontSize: 10, color: "#10b981", background: "rgba(16,185,129,0.08)", padding: "4px 8px", borderRadius: 4 }}>
            ✅ {files.length} file(s) {duration ? `(${(duration / 1000).toFixed(1)}s)` : ""}
          </div>
        )}
        {status === "error" && errorMsg && (
          <div style={{ fontSize: 10, color: "#ef4444", background: "rgba(239,68,68,0.08)", padding: "4px 8px", borderRadius: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            ❌ {errorMsg}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
          <button onClick={(e) => { e.stopPropagation(); onRun?.(); }} disabled={!isRunnable || isRunning}
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
              padding: "6px 8px", borderRadius: 6, border: "none", fontSize: 11, fontWeight: 600,
              cursor: isRunnable && !isRunning ? "pointer" : "not-allowed",
              background: isRunnable ? `linear-gradient(135deg, ${color}, ${color}cc)` : "var(--border-color)",
              color: isRunnable ? "#fff" : "var(--text-muted)", opacity: isRunning ? 0.7 : 1,
            }}>
            {isRunning ? <><Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> Running</> : <><Play size={11} /> Run</>}
          </button>
          {agentKey !== "mapping" && (
            <button onClick={(e) => { e.stopPropagation(); onViewInput?.(); }} title="View inputs"
              style={{ padding: "6px", borderRadius: 6, border: "1px solid var(--border-color)", background: "transparent", color: "var(--brand-primary)", cursor: "pointer", display: "flex" }}>
              <Eye size={12} />
            </button>
          )}
          <button onClick={(e) => { e.stopPropagation(); onViewOutput?.(); }} title="View outputs"
            style={{ padding: "6px", borderRadius: 6, border: "1px solid var(--border-color)", background: "transparent", color: "var(--success)", cursor: "pointer", display: "flex" }}>
            <FileCode2 size={12} />
          </button>
        </div>
      </div>

      {/* Handles — all 4 directions for flexible edge routing */}
      <Handle type="target" position={Position.Left} id="left" style={{ background: color, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} id="right" style={{ background: color, width: 8, height: 8 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ background: color, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ background: color, width: 8, height: 8 }} />
    </div>
  );
}

export const L5AgentNode = memo(L5AgentNodeInner);
