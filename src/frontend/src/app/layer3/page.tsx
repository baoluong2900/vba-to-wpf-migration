"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Search, ChevronRight, CheckCircle, AlertCircle, Copy, Save, RefreshCw, Code2, Wand2, Play, DatabaseZap, Table } from "lucide-react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import { format } from "sql-formatter";
const robustFormatSql = (sql: string): string => {
  if (!sql) return "";
  try {
    let formatted = format(sql, { language: 'postgresql', keywordCase: 'upper' });
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

const getPgSuggestion = (errMsg: string): { vn: string; jp: string } | null => {
  const errUpper = errMsg.toUpperCase();
  
  // 1. Table or view does not exist
  if (errUpper.includes("RELATION") && errUpper.includes("DOES NOT EXIST")) {
    return {
      vn: "Bảng hoặc View không tồn tại trên PostgreSQL. Hãy kiểm tra xem bảng đã được migrate/import sang PostgreSQL test database chưa.",
      jp: "テーブルまたはビューがPostgreSQLに存在しません。移行先のテスト環境DBに対象テーブルがインポートされているか確認してください。"
    };
  }
  
  // 2. Column does not exist
  if (errUpper.includes("COLUMN") && errUpper.includes("DOES NOT EXIST")) {
    return {
      vn: "Tên cột/trường không tồn tại hoặc sai chính tả. Vui lòng kiểm tra lại cấu trúc bảng trong Access vs PostgreSQL.",
      jp: "カラム名が存在しないか誤りがあります。AccessとPostgreSQL củaテーブル定義を確認してください。"
    };
  }
  
  // 3. Ambiguous column definition
  if (errUpper.includes("IS AMBIGUOUS")) {
    return {
      vn: "Tên cột bị trùng lặp giữa các bảng tham gia JOIN. Cần thêm alias (tên viết tắt của bảng) trước tên cột để phân biệt.",
      jp: "列の定義が曖昧です。JOIN結合する各テーブル間で列名が重複しているため、テーブル接頭辞（エイリアス）を指定してください。"
    };
  }
  
  // 4. Syntax errors
  if (errUpper.includes("SYNTAX ERROR")) {
    if (errUpper.includes("FROM")) {
      return {
        vn: "Lỗi cú pháp gần từ khóa FROM (thường do thừa/thiếu dấu phẩy phân tách các trường trong SELECT).",
        jp: "FROMキーワード付近に構文エラーがあります。SELECT句内のカラムの区切りカンマなどを確認してください。"
      };
    }
    return {
      vn: "Lỗi cú pháp SQL: Vui lòng kiểm tra kỹ các từ khóa, dấu đóng mở ngoặc hoặc dấu phẩy trong câu lệnh.",
      jp: "SQL構文エラーです。キーワード、カンマ、カッコの対応などを確認してください。"
    };
  }
  
  // 5. Data type casting error
  if (errUpper.includes("INVALID INPUT SYNTAX") || errUpper.includes("COULD NOT INTEGER")) {
    if (errUpper.includes("TIMESTAMP") || errUpper.includes("DATE")) {
      return {
        vn: "Lỗi định dạng ngày tháng (Date/Timestamp): Giá trị ngày tháng truyền vào không đúng định dạng PostgreSQL yêu cầu.",
        jp: "日付リテラルの書式エラーです。日付型の変換フォーマットを確認してください。"
      };
    }
    return {
      vn: "Lỗi chuyển đổi kiểu dữ liệu: Cố gắng so sánh hoặc nạp một chuỗi phi số vào trường kiểu số (Numeric/Integer).",
      jp: "無効な数値入力またはデータ型変換エラーです。カラムのデータ型と入力値を確認してください。"
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
  target_query?: Record<string, string>;
  description?: string;
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
  converted: "var(--success)",
  error:     "var(--danger)",
};
const STATUS_ICON: Record<string, string> = {
  pending:   "⬜",
  converted: "✅",
  error:     "❌",
};

// ── StatsBar ──────────────────────────────────────────────────────────────
function StatsBar({ stats }: { stats: Stats }) {
  const items = [
    { label: "Total",     value: stats.total,     color: "var(--info)" },
    { label: "Pending",   value: stats.pending,   color: "var(--text-muted)" },
    { label: "Converted", value: stats.converted, color: "var(--success)" },
    { label: "Error",     value: stats.error,     color: "var(--danger)" },
  ];
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      {items.map(({ label, value, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 9999, background: "var(--bg-tab-bar)", border: "1px solid var(--border-color)" }}>
          <span style={{ color, fontWeight: 800, fontSize: 16 }}>{value}</span>
          <span style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 600 }}>{label}</span>
        </div>
      ))}
      {/* Progress bar */}
      <div style={{ flex: 1, height: 7, background: "var(--border-color)", borderRadius: 9999, overflow: "hidden", maxWidth: 200 }}>
        <div style={{
          height: "100%", borderRadius: 9999,
          background: "linear-gradient(90deg, var(--success), var(--warning))",
          width: `${stats.total > 0 ? Math.round((stats.converted / stats.total) * 100) : 0}%`,
          transition: "width 0.4s ease",
        }} />
      </div>
      <span style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 600 }}>
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
    <div style={{ padding: "12px 16px", background: "var(--bg-tab-bar)", borderTop: "1px solid var(--border-color)", display: "flex", gap: 24, alignItems: "center", flexShrink: 0, fontSize: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: "var(--text-muted)" }}>Status:</span>
        <span style={{ color: STATUS_COLOR[status], fontWeight: 600 }}>
          {STATUS_ICON[status]} {status}
        </span>
      </div>
      {query.conversion_method && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Method:</span>
          <span style={{ color: "var(--brand-primary)", fontWeight: 600 }}>{query.conversion_method}</span>
        </div>
      )}
      {query.query_type && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Type:</span>
          <span style={{ color: "var(--info)" }}>{query.query_type}</span>
        </div>
      )}
      {query.tables && query.tables.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "var(--text-muted)" }}>Tables:</span>
          <span style={{ color: "var(--success)", fontFamily: "monospace" }}>
            {query.tables.slice(0, 3).join(", ")}{query.tables.length > 3 ? `... +${query.tables.length - 3}` : ""}
          </span>
        </div>
      )}

      {query.conversion_errors && query.conversion_errors.length > 0 && (
        <div style={{ color: "var(--danger)", fontSize: 11 }}>
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
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, border: "1px solid var(--border-color)", borderRadius: 8, background: "var(--bg-code)" }}>
      {/* Panel header */}
      <div style={{ padding: "8px 12px", background: "var(--bg-panel)", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-main)" }}>{title}</span>
        {badge && (
          <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: `${badgeColor}22`, color: badgeColor, fontWeight: 600 }}>
            {badge}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {editable && (
          <button onClick={handleFormat} title="Format SQL" style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent)", display: "flex", alignItems: "center", gap: 4, fontSize: 11, padding: "2px 6px" }}>
            <Code2 size={12} /> Format
          </button>
        )}
        <button onClick={copy} title="Copy SQL" style={{ background: "none", border: "none", cursor: "pointer", color: copied ? "var(--success)" : "var(--text-muted)", display: "flex", alignItems: "center", gap: 4, fontSize: 11, padding: "2px 6px" }}>
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
              background: editable ? "var(--bg-dark)" : "var(--bg-code)",
              fontFamily: "'Consolas', 'Monaco', 'Fira Code', monospace",
              fontSize: 12, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-all",
              color: "var(--text-main)",
              cursor: editable ? "text" : "default",
              borderLeft: editable ? "2px solid var(--accent)" : "2px solid var(--border-color)",
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
              background: "var(--bg-dark)",
              color: "var(--text-main)",
              fontFamily: "'Consolas', 'Monaco', 'Fira Code', monospace",
              fontSize: 12, lineHeight: 1.6, padding: 16,
              overflow: "auto",
              borderLeft: "2px solid var(--accent)",
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
            background: "color-mix(in srgb, var(--danger) 8%, transparent)",
            border: "1px solid color-mix(in srgb, var(--danger) 25%, transparent)",
            color: "var(--danger)",
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
          onMouseEnter={e => { e.currentTarget.style.background = "color-mix(in srgb, var(--danger) 15%, transparent)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "color-mix(in srgb, var(--danger) 8%, transparent)"; }}
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
              background: filterStatus === s ? "var(--accent)" : "var(--border-subtle)",
              color: filterStatus === s ? "#fff" : "var(--text-muted)" }}>
            {s}
          </button>
        ))}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: 20, color: "var(--text-muted)", fontSize: 12, textAlign: "center" }}>
            <div style={{ border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", width: 20, height: 20, animation: "spin 1s linear infinite", margin: "0 auto 8px" }} />
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
                style={{ padding: "8px 12px", cursor: "pointer", borderLeft: `3px solid ${isActive ? "var(--accent)" : "transparent"}`,
                  background: isActive ? "var(--accent-subtle)" : "transparent", transition: "all 0.15s",
                  display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ flexShrink: 0, fontSize: 12 }}>{STATUS_ICON[status]}</span>
                <span style={{ flex: 1, fontSize: 12, color: isActive ? "var(--accent)" : "var(--text-muted)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: isActive ? 600 : 400 }}
                  title={q.name}>{q.name}</span>
                {q.query_type && (
                  <span style={{ fontSize: 9, padding: "1px 4px", borderRadius: 3, background: "color-mix(in srgb, var(--brand-primary) 15%, transparent)", color: "var(--brand-primary)", flexShrink: 0 }}>
                    {q.query_type}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom actions */}
      <div style={{ padding: "10px 12px", borderTop: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: 6 }}>
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
                style={{ width: "100%", padding: "8px 10px 8px 30px", background: "var(--bg-dark)", border: "1px solid var(--border-color)", borderRadius: 6, color: "var(--text-main)", fontSize: 12 }}
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
            style={{ padding: "8px 12px", borderRadius: 6, background: "var(--bg-tab-bar)", border: "1px solid var(--border-color)", color: "var(--text-main)", fontSize: 13 }}
          >
            <option value="PostgreSQL">PostgreSQL</option>
            <option value="SQL Server">SQL Server</option>
            <option value="MySQL">MySQL</option>
          </select>
          <button 
            onClick={onConvert} disabled={converting}
            style={{ padding: "8px 16px", borderRadius: 8, background: "var(--brand-gradient)", color: "#fff", border: "none", cursor: converting ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, opacity: converting ? 0.7 : 1, boxShadow: "var(--shadow-glow)" }}
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
              <tr style={{ background: "var(--bg-dark)", color: "var(--text-muted)", textAlign: "left" }}>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-color)" }}>Name</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-color)" }}>Data Type</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-color)" }}>Length</th>
                <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-color)" }}>Required</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c: any, i: number) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border-color)" }}>
                  <td style={{ padding: "8px 12px", color: "var(--text-main)" }}>{c.logical_name || c.physical_name}</td>
                  <td style={{ padding: "8px 12px", color: "var(--info)" }}>{c.data_type}</td>
                  <td style={{ padding: "8px 12px", color: "var(--brand-primary)" }}>{c.length}</td>
                  <td style={{ padding: "8px 12px", color: String(c.required).toLowerCase() === "true" ? "var(--danger)" : "var(--success)" }}>{String(c.required)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-code)" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-panel)", color: "var(--text-main)", fontSize: 13, fontWeight: 600 }}>
            Generated DDL ({targetDb})
          </div>
          <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
            {tableDdl ? (
              <pre style={{ margin: 0, color: "var(--text-main)", fontSize: 13, fontFamily: "'Consolas', 'Monaco', monospace" }}>{tableDdl}</pre>
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
  const [editedTarget, setEditedTarget] = useState("");
  const [models, setModels]             = useState<string[]>([]);
  // "" = let the gateway use llm_settings.layer3_migration_model from config.json
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedDialect, setSelectedDialect] = useState("PostgreSQL");
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
      // The route returns an array on success and { success: false, error } otherwise
      setErrorLogs(Array.isArray(d) ? d : []);
      if (!Array.isArray(d)) showToast(`❌ ${d?.error || "Failed to fetch migration error logs"}`, false);
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

  // When selected changes, sync editedTarget and editedDescription
  useEffect(() => {
    setEditedTarget(robustFormatSql(selected?.target_sql || ""));
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
    setEditedTarget(robustFormatSql(q.target_sql || ""));
    // Fetch full detail if needed
    try {
      const r = await fetch(`/api/v1/layer3/queries/${encodeURIComponent(q.name)}`);
      const d = await r.json();
      if (d.success && d.result) {
        setSelected(d.result);
        setEditedTarget(robustFormatSql(d.result.target_sql || ""));
      }
    } catch {}
  };

  // AI Convert with typing effect
  const handleConvert = async () => {
    if (!selected) return;
    setConverting(true);
    setEditedTarget(""); // Clear for streaming effect
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
            setEditedTarget(fullText.substring(0, i));
            i += speed;
          } else {
            let formatted = fullText;
            try {
              formatted = format(fullText, { language: 'postgresql', keywordCase: 'upper' });
            } catch {}
            setEditedTarget(formatted); // ensure final text is set exactly and formatted
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
        showToast(d.error || d.detail || "Conversion failed", false);
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
    setEditedTarget("");
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
            setEditedTarget(fullText.substring(0, i));
            i += speed;
          } else {
            let formatted = fullText;
            try { formatted = format(fullText, { language: 'postgresql', keywordCase: 'upper' }); } catch {}
            setEditedTarget(formatted);
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
        showToast(d.error || d.detail || "Convert & Test failed", false);
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
    const finalTarget = robustFormatSql(editedTarget);
    setEditedTarget(finalTarget);
    try {
      const r = await fetch(`/api/v1/layer3/queries/${encodeURIComponent(selected.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_sql: finalTarget,
          description: editedDescription,
          model: selectedModel
        }),
      });
      const d = await r.json();
      if (d.success) {
        showToast("💾 Saved successfully!");
        await loadQueries();
      } else {
        showToast(d.error || d.detail || "Save failed", false);
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
          target_sql: editedTarget,
          query_name: selected.name,
        }),
      });
      const d = await r.json();
      setTestResult(d);

      // A static check (d.preview) runs nothing, so it never changes conversion_status.
      const updatedQuery = { ...selected, test_result: d };
      setSelected(updatedQuery);
      setQueries(prev => prev.map(q => q.name === selected.name ? updatedQuery : q));

      if (d.success) {
        showToast(d.preview ? "Static check passed — not executed" : "Query test passed");
      } else {
        showToast(`❌ ${d.preview ? "Static check failed" : "Query test failed"}${d.error_message ? `: ${d.error_message}` : ""}`, false);
      }
    } catch (e: any) {
      const errRes = { success: false, error_message: e.message };
      setTestResult(errRes);
      const updatedQuery = { ...selected, test_result: errRes };
      setSelected(updatedQuery);
      setQueries(prev => prev.map(q => q.name === selected.name ? updatedQuery : q));
      showToast(`Error: ${e.message}`, false);
    }
    setRunningTest(false);
  };


  const accessSql  = useMemo(() => {
    return robustFormatSql(selected?.raw_sql || "");
  }, [selected?.raw_sql]);
  const targetSql  = editedTarget;
  const hasDiff    = targetSql.trim() !== "" && targetSql !== accessSql;

  return (
    <>
      <Header />

      <main className="layout-content" style={{ flexDirection: "column" }}>
        <div className="ws-tabbar" style={{ padding: "0 16px" }}>
          <button onClick={() => setActiveTab("queries")} className={`ws-tab ${activeTab === "queries" ? "active" : ""}`} style={{ padding: "12px 16px" }}>
            <DatabaseZap size={16} /> Queries Migration
          </button>
          <button onClick={() => setActiveTab("tables")} className={`ws-tab ${activeTab === "tables" ? "active" : ""}`} style={{ padding: "12px 16px" }}>
            <Table size={16} /> Table Explorer
          </button>
        </div>

        <div key={activeTab} className="ws-panel-in" style={{ display: "flex", flex: 1, overflow: "hidden" }}>
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
              <div style={{ padding: "8px 16px", background: "var(--bg-tab-bar)", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 400 }}
                  title={selected.name}>{selected.name}</span>

                <div style={{ flex: 1 }} />

                {/* Token Estimator */}
                <span style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg-dark)", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border-color)" }} title="Estimated LLM prompt tokens (System + SQL)">
                  ⚡ ~{300 + Math.ceil(accessSql.length / 3.5)} tokens
                </span>

                {/* Model selector */}
                <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                  style={{ background: "var(--bg-panel)", border: "1px solid var(--border-color)", color: "var(--text-muted)", borderRadius: 6, padding: "4px 8px", fontSize: 12, outline: "none" }}>
                  <option value="">Default model (config.json)</option>
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>

                {/* Dialect selector */}
                <select value={selectedDialect} onChange={e => setSelectedDialect(e.target.value)}
                  style={{ background: "var(--bg-panel)", border: "1px solid var(--border-color)", color: "var(--text-muted)", borderRadius: 6, padding: "4px 8px", fontSize: 12, outline: "none", marginLeft: 8 }}>
                  <option value="PostgreSQL">PostgreSQL</option>
                  <option value="SQL Server">SQL Server</option>
                  <option value="MySQL">MySQL</option>
                </select>

                 <button onClick={handleRunTest} disabled={runningTest || !editedTarget || selectedDialect !== "PostgreSQL"}
                  style={{
                    background: "color-mix(in srgb, var(--success) 10%, transparent)",
                    border: "1px solid var(--success)",
                    color: "var(--success)",
                    borderRadius: 6,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: (runningTest || !editedTarget || selectedDialect !== "PostgreSQL") ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    opacity: (runningTest || !editedTarget || selectedDialect !== "PostgreSQL") ? 0.7 : 1
                  }}>
                  {runningTest ? (
                    <div className="loader" style={{ width: 12, height: 12 }} />
                  ) : (
                    <Play size={13} />
                  )}
                  {runningTest ? "Running..." : "▶ Run Test"}
                </button>

                <button onClick={handleSave} disabled={saving}
                  style={{ background: "color-mix(in srgb, var(--warning) 10%, transparent)", border: "1px solid var(--warning)", color: "var(--warning)", borderRadius: 6, padding: "6px 12px", fontSize: 12, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 6, opacity: saving ? 0.7 : 1 }}>
                  <Save size={13} /> {saving ? "Saving..." : "💾 Save"}
                </button>
              </div>

              {/* Description / Summary - Beautiful Editable Textbox */}
              <div style={{ padding: "8px 16px", background: "var(--accent-subtle)", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: 10, flexShrink: 0, fontSize: 13 }}>
                <span style={{ color: "var(--accent)", fontWeight: 700, display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
                  💡 Ý nghĩa SQL:
                </span>
                <input
                  type="text"
                  value={editedDescription}
                  onChange={e => setEditedDescription(e.target.value)}
                  placeholder="Mô tả ý nghĩa nghiệp vụ của câu SQL này..."
                  style={{
                    flex: 1,
                    background: "var(--bg-dark)",
                    border: "1px solid var(--accent-glow)",
                    color: "var(--text-main)",
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
                        background: (converting || convertingAndTesting) ? "var(--border-color)" : "var(--accent)",
                        border: "4px solid var(--bg-dark)",
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
                      title="Convert & Auto-Test: Đổi SQL rồi tự động test trên PostgreSQL DB, LLM tự fix nếu lỗi"
                      style={{
                        width: 32, height: 32, borderRadius: "50%",
                        background: (converting || convertingAndTesting) ? "var(--border-color)" : "var(--success)",
                        border: "4px solid var(--bg-dark)",
                        color: "#fff", cursor: (converting || convertingAndTesting) ? "not-allowed" : "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        boxShadow: "0 0 16px color-mix(in srgb, var(--success) 40%, transparent)",
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
                  sql={targetSql}
                  editable
                  onChange={setEditedTarget}
                  badge={hasDiff ? "Modified" : "PostgreSQL"}
                  badgeColor={hasDiff ? "var(--warning)" : "var(--success)"}
                />
              </div>

              {/* Test Result Panel (from Run Test or Convert & Auto-Test) */}
              {testResult && (
                <div style={{
                  padding: "16px",
                  background: "var(--bg-code)",
                  borderTop: "1px solid var(--border-color)",
                  borderBottom: "1px solid var(--border-color)",
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
                        background: testResult.success ? "color-mix(in srgb, var(--success) 15%, transparent)" : "color-mix(in srgb, var(--danger) 15%, transparent)",
                        color: testResult.success ? "var(--success)" : "var(--danger)"
                      }}>
                        {testResult.success ? "SUCCESS" : "ERROR"}
                      </span>
                      <span style={{ color: "var(--text-muted)", fontWeight: 600 }}>
                        PostgreSQL Test Result
                        {testHistory.length > 1 && (
                          <span style={{ marginLeft: 6, fontSize: 10, color: "var(--info)", fontWeight: 400 }}>
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
                          background: t.success ? "color-mix(in srgb, var(--success) 7%, transparent)" : "color-mix(in srgb, var(--danger) 7%, transparent)",
                          border: `1px solid ${t.success ? "color-mix(in srgb, var(--success) 20%, transparent)" : "color-mix(in srgb, var(--danger) 20%, transparent)"}`
                        }}>
                          <span style={{
                            fontSize: 10, fontWeight: 700, padding: "2px 5px", borderRadius: 3, flexShrink: 0,
                            background: t.success ? "color-mix(in srgb, var(--success) 20%, transparent)" : "color-mix(in srgb, var(--danger) 20%, transparent)",
                            color: t.success ? "var(--success)" : "var(--danger)"
                          }}>
                            {t.attempt === 0 ? "INIT" : `FIX ${t.attempt}`}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            {t.success
                              ? <span style={{ color: "var(--success)" }}>Passed ✔</span>
                              : <span style={{ color: "var(--danger)", fontFamily: "monospace", wordBreak: "break-all" }}>
                                  {t.error_code ? `${t.error_code}: ` : ""}{t.error_message}
                                </span>
                            }
                            {fixNotes[t.attempt] && (
                              <div style={{ marginTop: 3, color: "var(--info)", fontStyle: "italic", fontSize: 10 }}>
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
                      <div style={{ color: "var(--success)", fontWeight: 600 }}>
                        {testResult.message || "Query executed successfully."}
                      </div>
                      {testResult.preview?.columns ? (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", color: "var(--text-main)", textAlign: "left" }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid var(--border-color)", background: "var(--bg-panel)" }}>
                                {testResult.preview.columns.map((col: string, idx: number) => (
                                  <th key={idx} style={{ padding: "8px 12px", fontWeight: 600, color: "var(--info)" }}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {testResult.preview.rows && testResult.preview.rows.length > 0 ? (
                                testResult.preview.rows.map((row: any[], rowIdx: number) => (
                                  <tr key={rowIdx} style={{ borderBottom: "1px solid var(--border-color)", background: rowIdx % 2 === 0 ? "transparent" : "var(--bg-dark)" }}>
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
                          Rows affected: <span style={{ fontFamily: "monospace", color: "var(--info)", fontWeight: 700 }}>{testResult.preview.rowcount}</span>
                          <span style={{ marginLeft: 8, color: "var(--text-muted)", fontSize: 10 }}>(transaction rolled back)</span>
                        </div>
                      ) : null}

                      {/* Columns/rows from standard Run Test */}
                      {testResult.columns && (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", color: "var(--text-main)", textAlign: "left" }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid var(--border-color)", background: "var(--bg-panel)" }}>
                                {testResult.columns.map((col: string, idx: number) => (
                                  <th key={idx} style={{ padding: "8px 12px", fontWeight: 600, color: "var(--info)" }}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {testResult.rows && testResult.rows.length > 0 ? (
                                testResult.rows.map((row: any[], rowIdx: number) => (
                                  <tr key={rowIdx} style={{ borderBottom: "1px solid var(--border-color)", background: rowIdx % 2 === 0 ? "transparent" : "var(--bg-dark)" }}>
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
                            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>* Showing first {testResult.rows.length} row(s) from postgres_test</div>
                          )}
                        </div>
                      )}
                      {testResult.rowcount !== undefined && !testResult.preview && (
                        <div style={{ color: "var(--text-main)" }}>
                          Rows affected: <span style={{ fontFamily: "monospace", color: "var(--info)", fontWeight: 700 }}>{testResult.rowcount}</span>
                          <span style={{ marginLeft: 8, color: "var(--text-muted)", fontSize: 10 }}>(transaction rolled back)</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
                      <div style={{ padding: "12px", borderRadius: 6, background: "color-mix(in srgb, var(--danger) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--danger) 20%, transparent)", display: "flex", flexDirection: "column", gap: 6 }}>
                        {(testResult.error_code) && (
                          <div style={{ color: "var(--danger)", fontWeight: 700 }}>PostgreSQL Error: {testResult.error_code}</div>
                        )}
                        <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", color: "var(--danger)", fontFamily: "monospace", fontSize: 11 }}>
                          {testResult.error_message}
                        </pre>
                      </div>

                      {(() => {
                        const suggestions = getPgSuggestion(testResult.error_message || testResult.error_code || "");
                        if (!suggestions) return null;
                        return (
                          <div style={{
                            padding: "12px",
                            borderRadius: 6,
                            background: "color-mix(in srgb, var(--warning) 6%, transparent)",
                            border: "1px solid color-mix(in srgb, var(--warning) 20%, transparent)",
                            color: "var(--warning)"
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
        <div style={{ position: "fixed", bottom: 24, right: 24, background: toast.ok ? "var(--success)" : "var(--danger)", border: `1px solid ${toast.ok ? "var(--success)" : "var(--danger)"}`, color: "#ffffff", borderRadius: 8, padding: "10px 18px", fontSize: 13, fontWeight: 600, zIndex: 9999, boxShadow: "0 4px 20px rgba(0,0,0,0.4)", animation: "fadeIn 0.2s ease" }}>
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
          maxWidth: "100vw",
          height: "100dvh",
          background: "var(--bg-dark)",
          borderLeft: "1px solid var(--border-color)",
          boxShadow: "-10px 0 30px rgba(0,0,0,0.5)",
          zIndex: 1000,
          display: "flex",
          flexDirection: "column",
          animation: "slideIn 0.3s ease"
        }}>
          {/* Header */}
          <div style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--bg-panel)"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertCircle size={18} color="var(--danger)" />
              <span style={{ fontWeight: 700, color: "var(--text-main)", fontSize: 14 }}>Lịch sử lỗi Migration (PostgreSQL DB)</span>
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
                <div style={{ border: "2px solid var(--danger)", borderTopColor: "transparent", borderRadius: "50%", width: 24, height: 24, animation: "spin 1s linear infinite", marginBottom: 12 }} />
                <span>Đang tải danh sách lỗi...</span>
              </div>
            ) : errorLogs.length === 0 ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-muted)", gap: 8 }}>
                <CheckCircle size={32} color="var(--success)" />
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Tuyệt vời! Không phát hiện lỗi nào.</span>
              </div>
            ) : (
              errorLogs.map((log: any, idx: number) => {
                const dateStr = log.timestamp ? new Date(log.timestamp).toLocaleString() : "";
                const suggestions = getPgSuggestion(log.error_message || log.error_code || "");
                const errCode = log.error_code || log.error_message?.match(/[A-Z0-9]{5}/)?.[0] || "";
                
                return (
                  <div key={idx} style={{
                    background: "var(--bg-sidebar)",
                    border: "1px solid var(--border-color)",
                    borderRadius: 8,
                    padding: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    fontSize: 11
                  }}>
                    {/* Log Meta */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: "var(--info)" }}>{log.query_name}</span>
                      <span style={{ color: "var(--text-muted)", fontSize: 10 }}>{dateStr}</span>
                    </div>
                    
                    {/* Error Banner */}
                    <div style={{
                      background: "color-mix(in srgb, var(--danger) 8%, transparent)",
                      border: "1px solid color-mix(in srgb, var(--danger) 20%, transparent)",
                      borderRadius: 6,
                      padding: "8px 10px",
                      color: "var(--danger)"
                    }}>
                      <div style={{ fontWeight: 700, marginBottom: 4 }}>
                        {errCode ? errCode : "Error Detail"} {log.source_operation && `(${log.source_operation})`}
                      </div>
                      <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", fontFamily: "monospace", fontSize: 10 }}>
                        {log.error_message}
                      </pre>
                    </div>

                    {/* Dynamic Fix Suggestions */}
                    {suggestions && (
                      <div style={{
                        background: "color-mix(in srgb, var(--warning) 6%, transparent)",
                        border: "1px solid color-mix(in srgb, var(--warning) 20%, transparent)",
                        borderRadius: 6,
                        padding: "8px 10px",
                        color: "var(--warning)"
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
                        background: "var(--bg-code)",
                        border: "1px solid var(--border-color)",
                        borderRadius: 4,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        fontFamily: "monospace",
                        color: "var(--text-main)",
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
