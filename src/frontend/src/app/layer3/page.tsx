"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Search, ChevronDown, ChevronRight, Database, Zap, CheckCircle, Clock, AlertCircle, Copy, Save, RefreshCw, Code2, Wand2, Play, DatabaseZap, Table, Bot, FileSpreadsheet, Cpu, Sparkles } from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import { format } from "sql-formatter";
const robustFormatSql = (sql: string): string => {
  if (!sql) return "";
  try {
    let formatted = format(sql, { language: 'plsql', keywordCase: 'upper' });
    // Eliminate any consecutive blank lines to make the SQL extremely clean and compact
    return formatted.replace(/\n\s*\n/g, '\n').trim();
  } catch {
    let raw = sql;
    raw = raw.replace(/\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LEFT JOIN|RIGHT JOIN|INNER JOIN|HAVING)\b/gi, '\n$1\n  ');
    raw = raw.replace(/,\s*/g, ',\n  ');
    return raw.replace(/\n\s*\n/g, '\n').trim();
  }
};

const highlightSql = (text: string): string => {
  if (!text) return "";
  // Escape HTML
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Highlight Strings
  html = html.replace(/(['"])(.*?)\1/g, '<span style="color: #34d399;">$1$2$1</span>');

  // Highlight Comments
  html = html.replace(/(--.*)/g, '<span style="color: #6b7280; font-style: italic;">$1</span>');

  // Highlight Keywords
  const keywords = /\b(SELECT|FROM|WHERE|AND|OR|ON|LEFT|RIGHT|INNER|JOIN|GROUP BY|ORDER BY|HAVING|AS|INSERT|INTO|UPDATE|SET|DELETE|CREATE|TABLE|NULL|IS|NOT|IN|LIKE|WITH|UNION|ALL)\b/gi;
  html = html.replace(keywords, (match) => `<span style="color: #a78bfa; font-weight: bold;">${match.toUpperCase()}</span>`);

  // Highlight Custom functions
  const functions = /\b(IIF|FORMAT|LEFT|RIGHT|INSTR|SUBSTR|COUNT|SUM|AVG|MIN|MAX|NVL|COALESCE|TO_DATE|TO_CHAR|SYSDATE)\b/gi;
  html = html.replace(functions, (match) => `<span style="color: #f43f5e; font-weight: 600;">${match.toUpperCase()}</span>`);

  // Highlight brackets (Access style table/column references)
  html = html.replace(/(\[[^\]]+\])/g, '<span style="color: #38bdf8;">$1</span>');

  return html;
};

const getOraSuggestion = (errMsg: string): { vn: string; jp: string } | null => {
  const errUpper = errMsg.toUpperCase();
  if (errUpper.includes("ORA-00942") || errUpper.includes("TABLE OR VIEW DOES NOT EXIST")) {
    return {
      vn: "Bảng hoặc View không tồn tại trên Oracle. Hãy kiểm tra xem bảng đã được migrate/import sang database test (cổng 1523) chưa.",
      jp: "テーブルまたはビューが存在しません。移行先のテスト環境DB（ポート1523）に対象テーブルがインポートされているか確認してください。"
    };
  }
  if (errUpper.includes("ORA-00904") || errUpper.includes("INVALID IDENTIFIER")) {
    return {
      vn: "Tên cột/trường không tồn tại hoặc sai chính tả. Vui lòng kiểm tra lại cấu trúc bảng trong Access vs Oracle, hoặc xem lại ánh xạ logical_to_physical.",
      jp: "無効な識別子です。カラム名が正しいか、またはlogical_to_physicalによる物理名マッピングに誤りがないか確認してください。"
    };
  }
  if (errUpper.includes("ORA-00923") || errUpper.includes("FROM KEYWORD NOT FOUND")) {
    return {
      vn: "Lỗi cú pháp: Thiếu từ khóa FROM ở đúng vị trí (thường do thừa/thiếu dấu phẩy phân tách các trường trong câu lệnh SELECT).",
      jp: "FROMキーワードが見つかりません。SELECT句内のカラム句区切りカンマの過不足や構文エラーを確認してください。"
    };
  }
  if (errUpper.includes("ORA-00918") || errUpper.includes("COLUMN AMBIGUOUSLY DEFINED")) {
    return {
      vn: "Tên cột bị trùng lặp giữa các bảng tham gia JOIN. Cần thêm alias (tên viết tắt của bảng) trước tên cột để làm rõ nguồn.",
      jp: "列の定義が曖昧です。JOIN結合する各テーブル間で列名が重複しているため、テーブル接頭辞（エイリアス）を指定してください。"
    };
  }
  if (errUpper.includes("ORA-00936") || errUpper.includes("MISSING EXPRESSION")) {
    return {
      vn: "Lỗi cú pháp: Thiếu biểu thức (thường do dư thừa dấu phẩy ở cuối SELECT, hoặc viết sai các toán tử).",
      jp: "式が欠落しています。カンマが余分にあるか、演算子やカッコの閉じ忘れがないか確認してください。"
    };
  }
  if (errUpper.includes("ORA-00933") || errUpper.includes("SQL COMMAND NOT PROPERLY ENDED")) {
    return {
      vn: "Câu lệnh kết thúc không hợp lệ (ví dụ: dùng dấu chấm phẩy `;` ở cuối, hoặc viết sai thứ tự mệnh đề GROUP BY, ORDER BY, JOIN).",
      jp: "SQLコマンドが正しく終了されていません。セミコロン「;」の混入や、GROUP BY、ORDER BY等の記述順序を確認してください。"
    };
  }
  if (errUpper.includes("ORA-01722") || errUpper.includes("INVALID NUMBER")) {
    return {
      vn: "Lỗi chuyển đổi kiểu dữ liệu: Cố gắng chuyển đổi hoặc so sánh một chuỗi phi số với một trường kiểu số (Number).",
      jp: "数値が無効です。数値型カラムに対して非数値文字列の比較や代入を行っていないか確認してください。"
    };
  }
  if (errUpper.includes("ORA-01861") || errUpper.includes("LITERAL DOES NOT MATCH FORMAT STRING")) {
    return {
      vn: "Lỗi định dạng ngày tháng (Date/Timestamp): Giá trị ngày tháng truyền vào không đúng định dạng Oracle yêu cầu. Sử dụng TO_DATE(value, format).",
      jp: "リテラルが書式文字列と一致しません。日付型の変換時（TO_DATEなど）のフォーマットマスクが正しいか確認してください。"
    };
  }
  return null;
};


// ── Types ─────────────────────────────────────────────────────────────────
type ConversionStatus = "pending" | "converted" | "reviewed" | "error";

interface QueryItem {
  name: string;
  query_type?: string;
  tables?: string[];
  conversion_status?: ConversionStatus;
  conversion_method?: string;
  raw_sql?: string;
  target_sql?: string;
  oracle_query?: Record<string, string>;
  description?: string;
  conversion_notes?: string;
  conversion_errors?: string[];
  test_result?: any;
  test_history?: any[];
  fix_notes?: string[];
}

interface Stats {
  total: number;
  pending: number;
  converted: number;
  error: number;
}

// ── Constants ─────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  pending:   "var(--text-muted)",
  converted: "#10b981",
  error:     "#ef4444",
};
const STATUS_ICON: Record<string, string> = {
  pending:   "⬜",
  converted: "✅",
  error:     "❌",
};

// ── StatsBar ──────────────────────────────────────────────────────────────
function StatsBar({ stats }: { stats: Stats }) {
  const items = [
    { label: "Total",     value: stats.total,     color: "#60a5fa" },
    { label: "Pending",   value: stats.pending,   color: "var(--text-muted)" },
    { label: "Converted", value: stats.converted, color: "#10b981" },
    { label: "Error",     value: stats.error,     color: "#ef4444" },
  ];
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      {items.map(({ label, value, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color, fontWeight: 700, fontSize: 18 }}>{value}</span>
          <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{label}</span>
        </div>
      ))}
      {/* Progress bar */}
      <div style={{ flex: 1, height: 6, background: "#1f2937", borderRadius: 4, overflow: "hidden", maxWidth: 200 }}>
        <div style={{
          height: "100%", borderRadius: 4,
          background: "linear-gradient(90deg, #10b981, #f59e0b)",
          width: `${stats.total > 0 ? Math.round((stats.converted / stats.total) * 100) : 0}%`,
          transition: "width 0.4s ease",
        }} />
      </div>
      <span style={{ color: "var(--text-muted)", fontSize: 11 }}>
        {stats.total > 0 ? Math.round((stats.converted / stats.total) * 100) : 0}% done
      </span>
    </div>
  );
}

// ── ConversionInfo ────────────────────────────────────────────────────────
function ConversionInfo({ query }: { query: QueryItem | null }) {
  if (!query) return null;
  const status = query.conversion_status || "pending";
  return (
    <div style={{ padding: "12px 16px", background: "#151822", borderTop: "1px solid #2e3039", display: "flex", gap: 24, alignItems: "center", flexShrink: 0, fontSize: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: "var(--text-muted)" }}>Status:</span>
        <span style={{ color: STATUS_COLOR[status], fontWeight: 600 }}>
          {STATUS_ICON[status]} {status}
        </span>
      </div>
      {query.conversion_method && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Method:</span>
          <span style={{ color: "#a78bfa", fontWeight: 600 }}>{query.conversion_method}</span>
        </div>
      )}
      {query.query_type && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Type:</span>
          <span style={{ color: "#60a5fa" }}>{query.query_type}</span>
        </div>
      )}
      {query.tables && query.tables.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Tables:</span>
          <span style={{ color: "#34d399", fontFamily: "monospace" }}>
            {query.tables.slice(0, 3).join(", ")}{query.tables.length > 3 ? `... +${query.tables.length - 3}` : ""}
          </span>
        </div>
      )}

      {query.conversion_errors && query.conversion_errors.length > 0 && (
        <div style={{ color: "#ef4444", fontSize: 11 }}>
          ⚠ {query.conversion_errors[0]}
        </div>
      )}
    </div>
  );
}

// ── SqlPanel ─────────────────────────────────────────────────────────────
function SqlPanel({
  title, sql, editable, onChange, badge, badgeColor,
}: {
  title: string; sql: string; editable?: boolean;
  onChange?: (v: string) => void; badge?: string; badgeColor?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const copy = () => {
    navigator.clipboard.writeText(sql).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleFormat = () => {
    if (onChange && sql) {
      onChange(robustFormatSql(sql));
    }
  };

  const highlighted = useMemo(() => highlightSql(sql), [sql]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isEditing]);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, border: "1px solid #2e3039", borderRadius: 8, background: "#0d1117" }}>
      {/* Panel header */}
      <div style={{ padding: "8px 12px", background: "var(--bg-panel)", borderBottom: "1px solid #2e3039", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-main)" }}>{title}</span>
        {badge && (
          <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: `${badgeColor}22`, color: badgeColor, fontWeight: 600 }}>
            {badge}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {editable && (
          <button onClick={handleFormat} title="Format SQL" style={{ background: "none", border: "none", cursor: "pointer", color: "#60a5fa", display: "flex", alignItems: "center", gap: 4, fontSize: 11, padding: "2px 6px" }}>
            <Code2 size={12} /> Format
          </button>
        )}
        <button onClick={copy} title="Copy SQL" style={{ background: "none", border: "none", cursor: "pointer", color: copied ? "#10b981" : "var(--text-muted)", display: "flex", alignItems: "center", gap: 4, fontSize: 11, padding: "2px 6px" }}>
          <Copy size={12} /> {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      {/* SQL content */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {!editable || !isEditing ? (
          <pre
            onClick={() => { if (editable) setIsEditing(true); }}
            dangerouslySetInnerHTML={{ __html: highlighted || `<span style="color: #6b7280; font-style: italic;">No SQL provided</span>` }}
            style={{
              flex: 1, overflow: "auto", margin: 0, padding: 16,
              background: editable ? "#0f1520" : "#0d1117",
              fontFamily: "'Consolas', 'Monaco', 'Fira Code', monospace",
              fontSize: 12, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-all",
              color: "#e2e8f0",
              cursor: editable ? "text" : "default",
              borderLeft: editable ? "2px solid #3b82f6" : "2px solid #2e3039",
            }}
          />
        ) : (
          <textarea
            ref={textareaRef}
            value={sql}
            onChange={e => onChange?.(e.target.value)}
            onBlur={() => {
              if (onChange && sql) {
                onChange(robustFormatSql(sql));
              }
              setIsEditing(false);
            }}
            spellCheck={false}
            style={{
              flex: 1, resize: "none", border: "none", outline: "none",
              background: "#0f1520",
              color: "#e2e8f0",
              fontFamily: "'Consolas', 'Monaco', 'Fira Code', monospace",
              fontSize: 12, lineHeight: 1.6, padding: 16,
              overflow: "auto",
              borderLeft: "2px solid #3b82f6",
            }}
          />
        )}
      </div>
    </div>
  );
}

// ── QueryList ─────────────────────────────────────────────────────────────
function QueryList({
  queries, selected, onSelect, filterStatus, onFilterChange, loading,
  onShowErrorLogs, stats
}: {
  queries: QueryItem[]; selected: string | null; onSelect: (q: QueryItem) => void;
  filterStatus: string; onFilterChange: (s: string) => void;
  loading: boolean;
  onShowErrorLogs: () => void; stats: Stats;
}) {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => {
    let list = queries;
    if (filterStatus !== "all") list = list.filter(q => (q.conversion_status || "pending") === filterStatus);
    if (search.trim()) list = list.filter(q => q.name.toLowerCase().includes(search.toLowerCase()));
    return list;
  }, [queries, filterStatus, search]);

  return (
    <div className="task-sidebar" style={{ width: 280, flexShrink: 0, transition: "width 0.22s" }}>
      {/* Stats and Error Logs at the top of Sidebar */}
      <div style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: 10 }}>
        <StatsBar stats={stats} />
        
        <button
          onClick={onShowErrorLogs}
          style={{
            width: "100%",
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            color: "#ef4444",
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            transition: "all 0.2s"
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.08)"; }}
        >
          <AlertCircle size={13} />
          <span>Lịch sử lỗi SQL</span>
        </button>
      </div>

      {/* Search */}
      <div className="task-search-container">
        <div style={{ position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input
            type="text" placeholder="Search query..." value={search}
            onChange={e => setSearch(e.target.value)}
            className="task-search-input"
          />
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: "flex", padding: "6px 10px", gap: 4, borderBottom: "1px solid var(--border-color)", flexWrap: "wrap" }}>
        {["all", "pending", "converted", "error"].map(s => (
          <button key={s} onClick={() => onFilterChange(s)}
            style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, border: "none", cursor: "pointer", fontWeight: 600,
              background: filterStatus === s ? "#3b82f6" : "rgba(255,255,255,0.05)",
              color: filterStatus === s ? "#fff" : "var(--text-muted)" }}>
            {s}
          </button>
        ))}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: 20, color: "var(--text-muted)", fontSize: 12, textAlign: "center" }}>
            <div style={{ border: "2px solid #3b82f6", borderTopColor: "transparent", borderRadius: "50%", width: 20, height: 20, animation: "spin 1s linear infinite", margin: "0 auto 8px" }} />
            Loading queries...
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 20, color: "var(--text-muted)", fontSize: 12, textAlign: "center" }}>No queries found</div>
        ) : (
          filtered.map(q => {
            const status = q.conversion_status || "pending";
            const isActive = selected === q.name;
            return (
              <div key={q.name} onClick={() => onSelect(q)}
                style={{ padding: "8px 12px", cursor: "pointer", borderLeft: `3px solid ${isActive ? "#3b82f6" : "transparent"}`,
                  background: isActive ? "rgba(59,130,246,0.1)" : "transparent", transition: "all 0.15s",
                  display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ flexShrink: 0, fontSize: 12 }}>{STATUS_ICON[status]}</span>
                <span style={{ flex: 1, fontSize: 12, color: isActive ? "#93c5fd" : "#d1d5db",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: isActive ? 600 : 400 }}
                  title={q.name}>{q.name}</span>
                {q.query_type && (
                  <span style={{ fontSize: 9, padding: "1px 4px", borderRadius: 3, background: "rgba(167,139,250,0.15)", color: "#a78bfa", flexShrink: 0 }}>
                    {q.query_type}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom actions */}
      <div style={{ padding: "10px 12px", borderTop: "1px solid #2e3039", display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
          Loaded from queries
        </div>
      </div>
    </div>
  );
}


// ── Table Explorer Components ─────────────────────────────────────────────
function TableList({
  tables, selected, onSelect, loading
}: {
  tables: any[]; selected: string | null; onSelect: (t: any) => void; loading: boolean;
}) {
  const [search, setSearch] = useState("");
  const [taskSidebarCollapsed, setTaskSidebarCollapsed] = useState(false);

  const filtered = tables.filter(t => (t.table_name || "").toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="task-sidebar" style={{ width: taskSidebarCollapsed ? 40 : 280, overflow: "hidden", flexShrink: 0, transition: "width 0.22s" }}>
      <div style={{ display: "flex", padding: taskSidebarCollapsed ? "12px 8px" : "12px", borderBottom: "1px solid var(--border-color)", alignItems: "center", minHeight: 42 }}>
        {!taskSidebarCollapsed && <span style={{ color: "var(--text-muted)", fontSize: 12, fontWeight: 600, flex: 1 }}><strong style={{ color: "var(--text-main)" }}>Tables</strong> List</span>}
        <button 
          onClick={() => setTaskSidebarCollapsed(v => !v)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2, borderRadius: 4 }}
        >
          {taskSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
        </button>
      </div>

      {!taskSidebarCollapsed && (
        <>
          <div style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: 9, color: "var(--text-muted)" }} />
              <input
                type="text" placeholder="Search tables..." value={search} onChange={e => setSearch(e.target.value)}
                style={{ width: "100%", padding: "8px 10px 8px 30px", background: "#11141e", border: "1px solid var(--border-color)", borderRadius: 6, color: "var(--text-main)", fontSize: 12 }}
              />
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Total: {filtered.length} tables</div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
            {loading ? (
              <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 12 }}>Loading tables...</div>
            ) : filtered.length === 0 ? (
              <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 12 }}>No tables found.</div>
            ) : (
              filtered.map(t => {
                const name = t.table_name || "Unknown";
                const isSel = selected === name;
                return (
                  <div
                    key={name} onClick={() => onSelect(t)}
                    style={{
                      padding: "10px 12px", borderRadius: 6, cursor: "pointer", marginBottom: 4, display: "flex", alignItems: "center", gap: 8,
                      background: isSel ? "var(--accent-glow)" : "transparent",
                      border: isSel ? "1px solid var(--accent)" : "1px solid transparent",
                      color: isSel ? "var(--text-main)" : "var(--text-muted)",
                      transition: "all 0.2s"
                    }}
                  >
                    <Table size={14} style={{ color: isSel ? "var(--accent)" : "var(--text-muted)" }} />
                    <span style={{ fontSize: 13, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={name}>{name}</span>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}

function TableViewer({
  table, onConvert, targetDb, setTargetDb, tableDdl, converting
}: {
  table: any; onConvert: () => void; targetDb: string; setTargetDb: (db: string) => void; tableDdl: string; converting: boolean;
}) {
  if (!table) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", flexDirection: "column", gap: 12 }}>
        <Table size={48} style={{ opacity: 0.2 }} />
        <span>Select a table to view schema</span>
      </div>
    );
  }

  const columns = table.columns || [];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-main)", overflow: "hidden" }}>
      <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-panel)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, color: "var(--text-main)", display: "flex", alignItems: "center", gap: 8 }}>
            <Table size={20} color="var(--accent)" /> {table.table_name}
          </h2>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {columns.length} columns • {table.description || "No description"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select 
            value={targetDb} onChange={(e) => setTargetDb(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: 6, background: "#151822", border: "1px solid #2e3039", color: "var(--text-main)", fontSize: 13 }}
          >
            <option value="PostgreSQL">PostgreSQL</option>
            <option value="Oracle">Oracle</option>
            <option value="SQL Server">SQL Server</option>
            <option value="MySQL">MySQL</option>
          </select>
          <button 
            onClick={onConvert} disabled={converting}
            style={{ padding: "8px 16px", borderRadius: 6, background: "var(--accent)", color: "#fff", border: "none", cursor: converting ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, opacity: converting ? 0.7 : 1 }}
          >
            {converting ? <RefreshCw size={14} className="spin" /> : <Play size={14} />}
            {converting ? "Converting..." : "Convert Schema (Rule-based)"}
          </button>
        </div>
      </div>
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, borderRight: "1px solid var(--border-color)", overflowY: "auto", padding: 16 }}>
          <h3 style={{ fontSize: 14, marginTop: 0, marginBottom: 12, color: "var(--text-main)" }}>Access Columns</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#11141e", color: "var(--text-muted)", textAlign: "left" }}>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid #2e3039" }}>Name</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid #2e3039" }}>Data Type</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid #2e3039" }}>Length</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid #2e3039" }}>Required</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c: any, i: number) => (
                <tr key={i} style={{ borderBottom: "1px solid #2e3039" }}>
                  <td style={{ padding: "8px 12px", color: "var(--text-main)" }}>{c.logical_name || c.physical_name}</td>
                  <td style={{ padding: "8px 12px", color: "#60a5fa" }}>{c.data_type}</td>
                  <td style={{ padding: "8px 12px", color: "#a78bfa" }}>{c.length}</td>
                  <td style={{ padding: "8px 12px", color: String(c.required).toLowerCase() === "true" ? "#ef4444" : "#10b981" }}>{String(c.required)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#0d1117" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid #2e3039", background: "var(--bg-panel)", color: "var(--text-main)", fontSize: 13, fontWeight: 600 }}>
            Generated DDL ({targetDb})
          </div>
          <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
            {tableDdl ? (
              <pre style={{ margin: 0, color: "#e2e8f0", fontSize: 13, fontFamily: "'Consolas', 'Monaco', monospace" }}>{tableDdl}</pre>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: 13, fontStyle: "italic" }}>Click Convert to generate schema...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────
export default function Layer3Page() {
  const [activeTab, setActiveTab] = useState<"queries" | "tables">("queries");
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTable, setSelectedTable] = useState<any>(null);
  const [loadingTables, setLoadingTables] = useState(false);
  const [targetDb, setTargetDb] = useState("PostgreSQL");
  const [tableDdl, setTableDdl] = useState("");
  const [convertingTable, setConvertingTable] = useState(false);
  const [queries, setQueries]           = useState<QueryItem[]>([]);
  const [stats, setStats]               = useState<Stats>({ total: 0, pending: 0, converted: 0, error: 0 });
  const [selected, setSelected]         = useState<QueryItem | null>(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [loadingList, setLoadingList]   = useState(false);
  const [converting, setConverting]     = useState(false);
  const [saving, setSaving]             = useState(false);
  const [editedDescription, setEditedDescription] = useState("");
  const [editedOracle, setEditedOracle] = useState("");
  const [models, setModels]             = useState(["deepseek-v4-pro", "qwen3-vl-235b-a22b-thinking", "qwen-vl-plus-latest", "qwen-max", "qvq-max-2025-03-25"]);
  const [selectedModel, setSelectedModel] = useState("deepseek-v4-pro");
  const [selectedDialect, setSelectedDialect] = useState("Oracle SQL");
  const [toast, setToast]               = useState<{ msg: string; ok: boolean } | null>(null);
  const [runningTest, setRunningTest]   = useState(false);
  const [testResult, setTestResult]         = useState<any>(null);
  const [convertingAndTesting, setConvertingAndTesting] = useState(false);
  const [testHistory, setTestHistory]       = useState<any[]>([]);
  const [fixNotes, setFixNotes]             = useState<string[]>([]);

  const [showErrorLogs, setShowErrorLogs]   = useState(false);
  const [errorLogs, setErrorLogs]           = useState<any[]>([]);
  const [loadingErrorLogs, setLoadingErrorLogs] = useState(false);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const loadTables = async () => {
    setLoadingTables(true);
    try {
      const res = await fetch("/api/v1/layer3/tables");
      const data = await res.json();
      if (data.success && data.tables) {
        setTables(data.tables);
      }
    } catch (e) {
      console.error(e);
      showToast("❌ Failed to load tables", false);
    }
    setLoadingTables(false);
  };

  useEffect(() => {
    if (activeTab === "tables" && tables.length === 0) {
      loadTables();
    }
  }, [activeTab, tables.length]);

  const handleConvertTable = async () => {
    if (!selectedTable) return;
    setConvertingTable(true);
    try {
      const res = await fetch("/api/v1/layer3/tables/convert", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ table_name: selectedTable.table_name, target_db: targetDb })
      });
      const data = await res.json();
      if (data.success) {
        setTableDdl(data.ddl);
        showToast("✅ Schema converted successfully");
      } else {
        showToast("❌ Conversion failed: " + data.error, false);
      }
    } catch (e) {
      showToast("❌ Error converting schema", false);
    }
    setConvertingTable(false);
  };

  const loadErrorLogs = async () => {
    setLoadingErrorLogs(true);
    try {
      const r = await fetch(`/api/v1/layer3/migration_errors`);
      const d = await r.json();
      setErrorLogs(d || []);
    } catch {
      setErrorLogs([]);
      showToast("❌ Failed to fetch migration error logs", false);
    }
    setLoadingErrorLogs(false);
  };

  useEffect(() => {
    if (showErrorLogs) {
      loadErrorLogs();
    }
  }, [showErrorLogs]);

  // Load queries list
  const loadQueries = async () => {
    setLoadingList(true);
    try {
      const r = await fetch(`/api/v1/layer3/queries`);
      const d = await r.json();
      if (d.success) setQueries(d.queries || d.result || []);
    } catch {
      // If endpoint not yet implemented, use mock data
      setQueries([]);
    }
    setLoadingList(false);
  };

  // Tính toán stats từ list queries (vì đã fetch all)
  useEffect(() => {
    const s: Stats = { total: queries.length, pending: 0, converted: 0, error: 0 };
    queries.forEach(q => {
      if (q.conversion_status === "converted") s.converted++;
      else if (q.conversion_status === "error") s.error++;
      else s.pending++;
    });
    setStats(s);
  }, [queries]);

  // Load models
  useEffect(() => {
    fetch(`/api/v1/layer2/config`).then(r => r.json()).then(d => {
      if (d.models) setModels(d.models.map((m: any) => m.id));
    }).catch(() => {});
    loadQueries();
  }, []);

  // When selected changes, sync editedOracle and editedDescription
  useEffect(() => {
    setEditedOracle(robustFormatSql(selected?.target_sql || ""));
    setEditedDescription(selected?.description || "");
    if (selected && selected.test_result) {
      setTestResult(selected.test_result);
      setTestHistory(selected.test_history || []);
      setFixNotes(selected.fix_notes || []);
    } else {
      setTestResult(null);
      setTestHistory([]);
      setFixNotes([]);
    }
  }, [selected?.name, selected?.target_sql, selected?.description, selected?.test_result]);

  // Select query and load detail
  const handleSelect = async (q: QueryItem) => {
    setSelected(q);
    setEditedOracle(robustFormatSql(q.target_sql || ""));
    // Fetch full detail if needed
    try {
      const r = await fetch(`/api/v1/layer3/queries/${encodeURIComponent(q.name)}`);
      const d = await r.json();
      if (d.success && d.result) {
        setSelected(d.result);
        setEditedOracle(robustFormatSql(d.result.target_sql || ""));
      }
    } catch {}
  };

  // AI Convert with typing effect
  const handleConvert = async () => {
    if (!selected) return;
    setConverting(true);
    setEditedOracle(""); // Clear for streaming effect
    try {
      const r = await fetch(`/api/v1/layer3/convert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected.name, model: selectedModel, target_dialect: selectedDialect }),
      });
      const d = await r.json();
      if (d.success && d.result) {
        setSelected(d.result);
        setQueries(prev => prev.map(q => q.name === d.result.name ? d.result : q));
        
        // Simulated streaming effect
        const fullText = d.result.target_sql || "";
        let i = 0;
        const speed = Math.max(1, Math.floor(fullText.length / 40)); // adjusts speed based on length
        
        const interval = setInterval(() => {
          if (i <= fullText.length) {
            setEditedOracle(fullText.substring(0, i));
            i += speed;
          } else {
            let formatted = fullText;
            try {
              formatted = format(fullText, { language: 'tsql', keywordCase: 'upper' });
            } catch {}
            setEditedOracle(formatted); // ensure final text is set exactly and formatted
            clearInterval(interval);
            setConverting(false);
            if (d.errors && d.errors.length > 0) {
              showToast(`⚠️ AI fallback: ${d.errors.join(", ")}`, false);
            } else {
              showToast("✅ AI conversion successful!");
            }
          }
        }, 15);
      } else {
        setConverting(false);
        showToast(d.detail || "Conversion failed", false);
      }
    } catch (e: any) {
      setConverting(false);
      showToast(`Error: ${e.message}`, false);
    }
  };

  // Convert & Auto-Test (LLM Convert → test → auto-fix nếu lỗi)
  const handleConvertAndTest = async () => {
    if (!selected) return;
    setConvertingAndTesting(true);
    setTestResult(null);
    setTestHistory([]);
    setFixNotes([]);
    setEditedOracle("");
    try {
      const r = await fetch(`/api/v1/layer3/convert_and_test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected.name, model: selectedModel, max_fix_attempts: 2, target_dialect: selectedDialect }),
      });
      const d = await r.json();
      if (d.success && d.result) {
        const lastTest = d.last_test || {};
        setTestHistory(d.test_history || []);
        setFixNotes(d.fix_notes || []);
        setTestResult(lastTest);
        setSelected(d.result);
        setQueries(prev => prev.map(q => q.name === d.result.name ? d.result : q));

        // Streaming effect for final SQL
        const fullText = d.result.target_sql || "";
        let i = 0;
        const speed = Math.max(1, Math.floor(fullText.length / 40));
        const interval = setInterval(() => {
          if (i <= fullText.length) {
            setEditedOracle(fullText.substring(0, i));
            i += speed;
          } else {
            let formatted = fullText;
            try { formatted = format(fullText, { language: 'tsql', keywordCase: 'upper' }); } catch {}
            setEditedOracle(formatted);
            clearInterval(interval);
            setConvertingAndTesting(false);
            if (lastTest.success) {
              const fixCount = (d.fix_notes || []).length;
              if (fixCount > 0) {
                showToast(`✅ Converted & Fixed after ${fixCount} LLM correction(s)!`);
              } else {
                showToast("✅ Converted & Test passed on first try!");
              }
            } else {
              showToast("⚠️ Converted but test still fails — check errors below", false);
            }
          }
        }, 15);
      } else {
        setConvertingAndTesting(false);
        showToast(d.detail || "Convert & Test failed", false);
      }
    } catch (e: any) {
      setConvertingAndTesting(false);
      showToast(`Error: ${e.message}`, false);
    }
  };

  // Save
  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    const finalOracle = robustFormatSql(editedOracle);
    setEditedOracle(finalOracle);
    try {
      const r = await fetch(`/api/v1/layer3/queries/${encodeURIComponent(selected.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_sql: finalOracle,
          notes: selected.conversion_notes || "",
          description: editedDescription,
          model: selectedModel
        }),
      });
      const d = await r.json();
      if (d.success) {
        showToast("💾 Saved successfully!");
        await loadQueries();
      } else {
        showToast(d.detail || "Save failed", false);
      }
    } catch (e: any) {
      showToast(`Error: ${e.message}`, false);
    }
    setSaving(false);
  };

  // Run Test
  const handleRunTest = async () => {
    if (!selected) return;
    setRunningTest(true);
    setTestResult(null);
    try {
      const r = await fetch(`/api/v1/layer3/test_query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_sql: editedOracle,
          query_name: selected.name,
        }),
      });
      const d = await r.json();
      setTestResult(d);

      const updatedQuery = {
        ...selected,
        test_result: d,
        conversion_status: d.success ? ("converted" as const) : ("error" as const)
      };
      setSelected(updatedQuery);
      setQueries(prev => prev.map(q => q.name === selected.name ? updatedQuery : q));

      if (d.success) {
        showToast("🚀 Query test run executed successfully!");
      } else {
        showToast("❌ Query test run failed!", false);
      }
    } catch (e: any) {
      const errRes = { success: false, error_message: e.message };
      setTestResult(errRes);
      const updatedQuery = {
        ...selected,
        test_result: errRes,
        conversion_status: "error" as const
      };
      setSelected(updatedQuery);
      setQueries(prev => prev.map(q => q.name === selected.name ? updatedQuery : q));
      showToast(`Error: ${e.message}`, false);
    }
    setRunningTest(false);
  };


  const accessSql  = useMemo(() => {
    return robustFormatSql(selected?.raw_sql || "");
  }, [selected?.raw_sql]);
  const oracleSql  = editedOracle;
  const hasDiff    = oracleSql.trim() !== "" && oracleSql !== accessSql;

  return (
    <>
      <Header />

      <main className="layout-content" style={{ flexDirection: "column" }}>
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-color)", background: "var(--bg-panel)", padding: "0 16px", flexShrink: 0 }}>
          <div onClick={() => setActiveTab("queries")} style={{ padding: "12px 16px", cursor: "pointer", borderBottom: activeTab === "queries" ? "2px solid var(--accent)" : "2px solid transparent", color: activeTab === "queries" ? "var(--text-main)" : "var(--text-muted)", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <DatabaseZap size={16} /> Queries Migration
          </div>
          <div onClick={() => setActiveTab("tables")} style={{ padding: "12px 16px", cursor: "pointer", borderBottom: activeTab === "tables" ? "2px solid var(--accent)" : "2px solid transparent", color: activeTab === "tables" ? "var(--text-main)" : "var(--text-muted)", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <Table size={16} /> Table Explorer
          </div>
        </div>

        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {activeTab === "queries" ? (
          <>
            <QueryList
              queries={queries} selected={selected?.name || null} onSelect={handleSelect}
              filterStatus={filterStatus} onFilterChange={setFilterStatus}
              loading={loadingList}
              onShowErrorLogs={() => setShowErrorLogs(true)}
              stats={stats}
            />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selected ? (
            <div key={selected.name} style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
              {/* Toolbar */}
              <div style={{ padding: "8px 16px", background: "#151822", borderBottom: "1px solid #2e3039", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 400 }}
                  title={selected.name}>{selected.name}</span>

                <div style={{ flex: 1 }} />

                {/* Token Estimator */}
                <span style={{ fontSize: 11, color: "var(--text-muted)", background: "#1f2937", padding: "4px 8px", borderRadius: 4, border: "1px solid #374151" }} title="Estimated LLM prompt tokens (System + SQL)">
                  ⚡ ~{300 + Math.ceil(accessSql.length / 3.5)} tokens
                </span>

                {/* Model selector */}
                <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                  style={{ background: "var(--bg-panel)", border: "1px solid #374151", color: "#d1d5db", borderRadius: 6, padding: "4px 8px", fontSize: 12, outline: "none" }}>
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>

                {/* Dialect selector */}
                <select value={selectedDialect} onChange={e => setSelectedDialect(e.target.value)}
                  style={{ background: "var(--bg-panel)", border: "1px solid #374151", color: "#d1d5db", borderRadius: 6, padding: "4px 8px", fontSize: 12, outline: "none", marginLeft: 8 }}>
                  <option value="Oracle SQL">Oracle SQL</option>
                  <option value="PostgreSQL">PostgreSQL</option>
                  <option value="SQL Server">SQL Server</option>
                  <option value="MySQL">MySQL</option>
                </select>

                 <button onClick={handleRunTest} disabled={runningTest || !editedOracle || selectedDialect !== "Oracle SQL"}
                  style={{
                    background: "rgba(16,185,129,0.1)",
                    border: "1px solid #10b981",
                    color: "#34d399",
                    borderRadius: 6,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: (runningTest || !editedOracle || selectedDialect !== "Oracle SQL") ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    opacity: (runningTest || !editedOracle || selectedDialect !== "Oracle SQL") ? 0.7 : 1
                  }}>
                  {runningTest ? (
                    <div className="loader" style={{ width: 12, height: 12 }} />
                  ) : (
                    <Play size={13} />
                  )}
                  {runningTest ? "Running..." : "▶ Run Test"}
                </button>

                <button onClick={handleSave} disabled={saving}
                  style={{ background: "rgba(245,158,11,0.1)", border: "1px solid #f59e0b", color: "#fbbf24", borderRadius: 6, padding: "6px 12px", fontSize: 12, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 6, opacity: saving ? 0.7 : 1 }}>
                  <Save size={13} /> {saving ? "Saving..." : "💾 Save"}
                </button>
              </div>

              {/* Description / Summary - Beautiful Editable Textbox */}
              <div style={{ padding: "8px 16px", background: "rgba(59,130,246,0.06)", borderBottom: "1px solid #2e3039", display: "flex", alignItems: "center", gap: 10, flexShrink: 0, fontSize: 13 }}>
                <span style={{ color: "#60a5fa", fontWeight: 700, display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
                  💡 Ý nghĩa SQL:
                </span>
                <input
                  type="text"
                  value={editedDescription}
                  onChange={e => setEditedDescription(e.target.value)}
                  placeholder="Mô tả ý nghĩa nghiệp vụ của câu SQL này..."
                  style={{
                    flex: 1,
                    background: "rgba(30,41,59,0.5)",
                    border: "1px solid rgba(59,130,246,0.25)",
                    color: "#e2e8f0",
                    borderRadius: 6,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontStyle: "italic",
                    outline: "none"
                  }}
                />
              </div>

              {/* 2-panel SQL view */}
              <div style={{ flex: 1, display: "flex", overflow: "hidden", gap: 0 }}>
                {/* Access SQL */}
                <SqlPanel
                  title="Access SQL (Source)"
                  sql={accessSql}
                  badge="Access"
                  badgeColor="#a78bfa"
                />
                {/* Center Divider with 2 Convert Buttons */}
                <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", width: 1, background: "var(--border-color)", flexShrink: 0, zIndex: 10 }}>
                  {/* Standard AI Convert (blue) */}
                  <div style={{ position: "absolute", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                    <button onClick={handleConvert} disabled={converting || convertingAndTesting}
                      title="AI Convert: Access → Target SQL"
                      style={{
                        width: 32, height: 32, borderRadius: "50%",
                        background: (converting || convertingAndTesting) ? "var(--border-color)" : "#3b82f6",
                        border: "4px solid #0f1115",
                        color: "#fff", cursor: (converting || convertingAndTesting) ? "not-allowed" : "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        boxShadow: "0 0 10px rgba(0,0,0,0.5)",
                        transition: "transform 0.2s"
                      }}
                      onMouseEnter={(e) => { if (!converting && !convertingAndTesting) e.currentTarget.style.transform = "scale(1.1)"; }}
                      onMouseLeave={(e) => { if (!converting && !convertingAndTesting) e.currentTarget.style.transform = "scale(1)"; }}
                    >
                      {converting ? <div style={{ border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", width: 12, height: 12, animation: "spin 1s linear infinite" }} /> : <Wand2 size={14} strokeWidth={2.5} />}
                    </button>
                    {/* Convert & Auto-Test (green) */}
                    <button onClick={handleConvertAndTest} disabled={converting || convertingAndTesting}
                      title="Convert & Auto-Test: Đổi SQL rồi tự động test trên Oracle DB, LLM tự fix nếu lỗi"
                      style={{
                        width: 32, height: 32, borderRadius: "50%",
                        background: (converting || convertingAndTesting) ? "var(--border-color)" : "#10b981",
                        border: "4px solid #0f1115",
                        color: "#fff", cursor: (converting || convertingAndTesting) ? "not-allowed" : "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        boxShadow: "0 0 16px rgba(16,185,129,0.4)",
                        transition: "transform 0.2s"
                      }}
                      onMouseEnter={(e) => { if (!converting && !convertingAndTesting) e.currentTarget.style.transform = "scale(1.1)"; }}
                      onMouseLeave={(e) => { if (!converting && !convertingAndTesting) e.currentTarget.style.transform = "scale(1)"; }}
                    >
                      {convertingAndTesting
                        ? <div style={{ border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", width: 12, height: 12, animation: "spin 1s linear infinite" }} />
                        : <Play size={14} strokeWidth={2.5} />}
                    </button>
                  </div>
                </div>
                {/* Target SQL */}
                <SqlPanel
                  title="Target SQL (Target)"
                  sql={oracleSql}
                  editable
                  onChange={setEditedOracle}
                  badge={hasDiff ? "Modified" : "Oracle"}
                  badgeColor={hasDiff ? "#f59e0b" : "#10b981"}
                />
              </div>

              {/* Test Result Panel (from Run Test or Convert & Auto-Test) */}
              {testResult && (
                <div style={{
                  padding: "16px",
                  background: "#0d1117",
                  borderTop: "1px solid #2e3039",
                  borderBottom: "1px solid #2e3039",
                  maxHeight: "360px",
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  fontSize: 12
                }}>
                  {/* Header */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{
                        padding: "4px 8px", borderRadius: 4, fontWeight: 700,
                        background: testResult.success ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                        color: testResult.success ? "#10b981" : "#ef4444"
                      }}>
                        {testResult.success ? "SUCCESS" : "ERROR"}
                      </span>
                      <span style={{ color: "var(--text-muted)", fontWeight: 600 }}>
                        Oracle Test Result
                        {testHistory.length > 1 && (
                          <span style={{ marginLeft: 6, fontSize: 10, color: "#60a5fa", fontWeight: 400 }}>
                            ({testHistory.length} attempt{testHistory.length > 1 ? "s" : ""}, {fixNotes.length} LLM fix{fixNotes.length !== 1 ? "es" : ""})
                          </span>
                        )}
                      </span>
                    </div>
                    <button onClick={() => { setTestResult(null); setTestHistory([]); setFixNotes([]); }}
                      style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 11 }}>
                      ✕ Close
                    </button>
                  </div>

                  {/* Fix timeline (only when there were multiple attempts) */}
                  {testHistory.length > 1 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>Fix Timeline</div>
                      {testHistory.map((t: any, idx: number) => (
                        <div key={idx} style={{
                          display: "flex", alignItems: "flex-start", gap: 8,
                          padding: "6px 10px", borderRadius: 6,
                          background: t.success ? "rgba(16,185,129,0.07)" : "rgba(239,68,68,0.07)",
                          border: `1px solid ${t.success ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`
                        }}>
                          <span style={{
                            fontSize: 10, fontWeight: 700, padding: "2px 5px", borderRadius: 3, flexShrink: 0,
                            background: t.success ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)",
                            color: t.success ? "#10b981" : "#ef4444"
                          }}>
                            {t.attempt === 0 ? "INIT" : `FIX ${t.attempt}`}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            {t.success
                              ? <span style={{ color: "#34d399" }}>Passed ✔</span>
                              : <span style={{ color: "#fca5a5", fontFamily: "monospace", wordBreak: "break-all" }}>
                                  {t.error_code ? `ORA-${t.error_code}: ` : ""}{t.error_message}
                                </span>
                            }
                            {fixNotes[t.attempt] && (
                              <div style={{ marginTop: 3, color: "#60a5fa", fontStyle: "italic", fontSize: 10 }}>
                                ↳ {fixNotes[t.attempt]}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Final test result detail */}
                  {testResult.success ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ color: "#34d399", fontWeight: 600 }}>
                        {testResult.message || "Query executed successfully."}
                      </div>
                      {testResult.preview?.columns ? (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", color: "var(--text-main)", textAlign: "left" }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid #2e3039", background: "var(--bg-panel)" }}>
                                {testResult.preview.columns.map((col: string, idx: number) => (
                                  <th key={idx} style={{ padding: "8px 12px", fontWeight: 600, color: "#60a5fa" }}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {testResult.preview.rows && testResult.preview.rows.length > 0 ? (
                                testResult.preview.rows.map((row: any[], rowIdx: number) => (
                                  <tr key={rowIdx} style={{ borderBottom: "1px solid #1f2937", background: rowIdx % 2 === 0 ? "transparent" : "var(--bg-dark)" }}>
                                    {row.map((val: any, colIdx: number) => (
                                      <td key={colIdx} style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                                        {val === null ? <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>NULL</span> : String(val)}
                                      </td>
                                    ))}
                                  </tr>
                                ))
                              ) : (
                                <tr><td colSpan={testResult.preview.columns.length || 1} style={{ padding: "12px", color: "var(--text-muted)", fontStyle: "italic", textAlign: "center" }}>No rows returned</td></tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      ) : testResult.preview?.rowcount !== undefined ? (
                        <div style={{ color: "var(--text-main)" }}>
                          Rows affected: <span style={{ fontFamily: "monospace", color: "#60a5fa", fontWeight: 700 }}>{testResult.preview.rowcount}</span>
                          <span style={{ marginLeft: 8, color: "var(--text-muted)", fontSize: 10 }}>(transaction rolled back)</span>
                        </div>
                      ) : null}

                      {/* Columns/rows from standard Run Test */}
                      {testResult.columns && (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", color: "var(--text-main)", textAlign: "left" }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid #2e3039", background: "var(--bg-panel)" }}>
                                {testResult.columns.map((col: string, idx: number) => (
                                  <th key={idx} style={{ padding: "8px 12px", fontWeight: 600, color: "#60a5fa" }}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {testResult.rows && testResult.rows.length > 0 ? (
                                testResult.rows.map((row: any[], rowIdx: number) => (
                                  <tr key={rowIdx} style={{ borderBottom: "1px solid #1f2937", background: rowIdx % 2 === 0 ? "transparent" : "var(--bg-dark)" }}>
                                    {row.map((val: any, colIdx: number) => (
                                      <td key={colIdx} style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                                        {val === null ? <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>NULL</span> : String(val)}
                                      </td>
                                    ))}
                                  </tr>
                                ))
                              ) : (
                                <tr><td colSpan={testResult.columns.length || 1} style={{ padding: "12px", color: "var(--text-muted)", fontStyle: "italic", textAlign: "center" }}>No rows returned</td></tr>
                              )}
                            </tbody>
                          </table>
                          {testResult.rows && testResult.rows.length > 0 && (
                            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>* Showing first {testResult.rows.length} row(s) from oracle_test</div>
                          )}
                        </div>
                      )}
                      {testResult.rowcount !== undefined && !testResult.preview && (
                        <div style={{ color: "var(--text-main)" }}>
                          Rows affected: <span style={{ fontFamily: "monospace", color: "#60a5fa", fontWeight: 700 }}>{testResult.rowcount}</span>
                          <span style={{ marginLeft: 8, color: "var(--text-muted)", fontSize: 10 }}>(transaction rolled back)</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
                      <div style={{ padding: "12px", borderRadius: 6, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", display: "flex", flexDirection: "column", gap: 6 }}>
                        {(testResult.error_code) && (
                          <div style={{ color: "#fca5a5", fontWeight: 700 }}>Oracle Error: {testResult.error_code}</div>
                        )}
                        <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", color: "#fca5a5", fontFamily: "monospace", fontSize: 11 }}>
                          {testResult.error_message}
                        </pre>
                      </div>

                      {(() => {
                        const matchedOra = testResult.error_message?.match(/ORA-\d+/)?.[0] || (testResult.error_code ? `ORA-${testResult.error_code}` : "");
                        const suggestions = getOraSuggestion(matchedOra || testResult.error_message || "");
                        if (!suggestions) return null;
                        return (
                          <div style={{
                            padding: "12px",
                            borderRadius: 6,
                            background: "rgba(245, 158, 11, 0.06)",
                            border: "1px solid rgba(245, 158, 11, 0.2)",
                            color: "#fde047"
                          }}>
                            <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
                              💡 Gợi ý sửa lỗi (Fix Suggestion):
                            </div>
                            <div style={{ lineHeight: 1.4, fontSize: 11 }}>
                              <strong>VN:</strong> {suggestions.vn}
                              <br />
                              <strong>JP:</strong> {suggestions.jp}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}


              {/* Conversion Info */}
              <ConversionInfo query={selected} />
            </div>
          ) : (
            /* Empty state */
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", gap: 16 }}>
              <span style={{ fontSize: 56, opacity: 0.4 }}>🗄</span>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-muted)", marginBottom: 6 }}>Select a query to convert</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Choose from the list on the left, then click 🤖 AI Convert</div>
              </div>
            </div>
          )}
        </div>
          </>
        ) : (
          <>
            <TableList 
              tables={tables} loading={loadingTables} selected={selectedTable?.table_name || null} 
              onSelect={(t) => { setSelectedTable(t); setTableDdl(""); }} 
            />
            <TableViewer 
              table={selectedTable} onConvert={handleConvertTable} targetDb={targetDb} setTargetDb={setTargetDb} 
              tableDdl={tableDdl} converting={convertingTable} 
            />
          </>
        )}
        </div>
      </main>
      <Footer />

      {/* Toast */}
      {toast && (
        <div style={{ position: "fixed", bottom: 24, right: 24, background: toast.ok ? "#064e3b" : "#7f1d1d", border: `1px solid ${toast.ok ? "#10b981" : "#ef4444"}`, color: toast.ok ? "#34d399" : "#fca5a5", borderRadius: 8, padding: "10px 18px", fontSize: 13, fontWeight: 600, zIndex: 9999, boxShadow: "0 4px 20px rgba(0,0,0,0.4)", animation: "fadeIn 0.2s ease" }}>
          {toast.msg}
        </div>
      )}

      {/* Sliding Side Panel for Error Logs */}
      {showErrorLogs && (
        <div style={{
          position: "fixed",
          top: 0,
          right: 0,
          width: 500,
          height: "100vh",
          background: "#0f111a",
          borderLeft: "1px solid #2e3039",
          boxShadow: "-10px 0 30px rgba(0,0,0,0.5)",
          zIndex: 1000,
          display: "flex",
          flexDirection: "column",
          animation: "slideIn 0.3s ease"
        }}>
          {/* Header */}
          <div style={{
            padding: "16px 20px",
            borderBottom: "1px solid #2e3039",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#161824"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertCircle size={18} color="#ef4444" />
              <span style={{ fontWeight: 700, color: "var(--text-main)", fontSize: 14 }}>Lịch sử lỗi Migration (Oracle DB)</span>
            </div>
            <button
              onClick={() => setShowErrorLogs(false)}
              style={{
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                fontSize: 18,
                fontWeight: 300
              }}
            >
              ✕
            </button>
          </div>

          {/* Log List */}
          <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
            {loadingErrorLogs ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-muted)" }}>
                <div style={{ border: "2px solid #ef4444", borderTopColor: "transparent", borderRadius: "50%", width: 24, height: 24, animation: "spin 1s linear infinite", marginBottom: 12 }} />
                <span>Đang tải danh sách lỗi...</span>
              </div>
            ) : errorLogs.length === 0 ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-muted)", gap: 8 }}>
                <CheckCircle size={32} color="#10b981" />
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Tuyệt vời! Không phát hiện lỗi nào.</span>
              </div>
            ) : (
              errorLogs.map((log: any, idx: number) => {
                const dateStr = log.timestamp ? new Date(log.timestamp).toLocaleString() : "";
                const matchedOra = log.error_message?.match(/ORA-\d+/)?.[0] || (log.error_code ? `ORA-${log.error_code}` : "");
                const suggestions = getOraSuggestion(matchedOra || log.error_message || "");
                
                return (
                  <div key={idx} style={{
                    background: "#1c1e29",
                    border: "1px solid #2e3039",
                    borderRadius: 8,
                    padding: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    fontSize: 11
                  }}>
                    {/* Log Meta */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: "#60a5fa" }}>{log.query_name}</span>
                      <span style={{ color: "var(--text-muted)", fontSize: 10 }}>{dateStr}</span>
                    </div>
                    
                    {/* Error Banner */}
                    <div style={{
                      background: "rgba(239, 68, 68, 0.08)",
                      border: "1px solid rgba(239, 68, 68, 0.2)",
                      borderRadius: 6,
                      padding: "8px 10px",
                      color: "#fca5a5"
                    }}>
                      <div style={{ fontWeight: 700, marginBottom: 4 }}>
                        {matchedOra ? matchedOra : "Error Detail"} {log.source_operation && `(${log.source_operation})`}
                      </div>
                      <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", fontFamily: "monospace", fontSize: 10 }}>
                        {log.error_message}
                      </pre>
                    </div>

                    {/* Dynamic Fix Suggestions */}
                    {suggestions && (
                      <div style={{
                        background: "rgba(245, 158, 11, 0.06)",
                        border: "1px solid rgba(245, 158, 11, 0.2)",
                        borderRadius: 6,
                        padding: "8px 10px",
                        color: "#fde047"
                      }}>
                        <div style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                          💡 Gợi ý sửa lỗi (Fix Suggestion):
                        </div>
                        <div style={{ lineHeight: 1.4 }}>
                          <strong>VN:</strong> {suggestions.vn}
                          <br />
                          <strong>JP:</strong> {suggestions.jp}
                        </div>
                      </div>
                    )}

                    {/* SQL Collapsible */}
                    <details style={{ cursor: "pointer" }}>
                      <summary style={{ color: "var(--text-muted)", fontWeight: 600, outline: "none", userSelect: "none" }}>Xem câu lệnh SQL</summary>
                      <pre style={{
                        marginTop: 6,
                        padding: 8,
                        background: "#0d1117",
                        border: "1px solid #1f2937",
                        borderRadius: 4,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        fontFamily: "monospace",
                        color: "#e2e8f0",
                        fontSize: 10
                      }}>
                        {log.sql}
                      </pre>
                    </details>
                  </div>
                );
              }).reverse() // Show newest first
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  );
}
