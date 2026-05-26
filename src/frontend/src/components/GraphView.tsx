"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// ── Neo4j-style type config ──────────────────────────────────────────────────
const TYPE_CFG: Record<string, {
  icon: string; color: string; bg: string; ring: string; abbr: string;
}> = {
  form:    { icon: "⬡", color: "#4c9ef8", bg: "#1a3a6e", ring: "#4c9ef8", abbr: "F"  },
  report:  { icon: "📄", color: "#72b7f7", bg: "#122c52", ring: "#72b7f7", abbr: "R"  },
  module:  { icon: "⚙",  color: "#34d399", bg: "#063520", ring: "#34d399", abbr: "M"  },
  macro:   { icon: "⚡", color: "#f97316", bg: "#3b1300", ring: "#f97316", abbr: "MC" },
  query:   { icon: "🗄",  color: "#a3e635", bg: "#1a2e05", ring: "#a3e635", abbr: "Q"  },
  event:   { icon: "▶",  color: "#c084fc", bg: "#2e1060", ring: "#c084fc", abbr: "EV" },
  view:       { icon: "◈",  color: "#22d3ee", bg: "#083344", ring: "#22d3ee", abbr: "V"  },
  viewmodel:  { icon: "◇",  color: "#a78bfa", bg: "#2e1060", ring: "#a78bfa", abbr: "VM" },
  handler:    { icon: "▸",  color: "#f472b6", bg: "#3f0d28", ring: "#f472b6", abbr: "H"  },
  repository: { icon: "⬢",  color: "#4ade80", bg: "#052e16", ring: "#4ade80", abbr: "Rep" },
  service:    { icon: "◎",  color: "#2dd4bf", bg: "#042f2e", ring: "#2dd4bf", abbr: "S"  },
  workflow:   { icon: "⚡", color: "#fb923c", bg: "#3b1300", ring: "#fb923c", abbr: "W"  },
};

TYPE_CFG.navigation = { icon: "->", color: "#38bdf8", bg: "#082f49", ring: "#38bdf8", abbr: "Nav" };
TYPE_CFG.warning = { icon: "!", color: "#facc15", bg: "#3f2f05", ring: "#facc15", abbr: "Warn" };

interface GraphStats {
  nodes: number;
  edges: number;
  events?: number;
  macros?: number;
  modules?: number;
  queries?: number;
  forms?: number;
  views?: number;
  viewmodels?: number;
  handlers?: number;
  repositories?: number;
  services?: number;
  navigation?: number;
  warnings?: number;
  workflows?: number;
}
interface NodeData {
  id: string;
  label: string;
  type: string;
  badge?: string;
  vbaLabel?: string;
  mappingStatus?: "mapped" | "fallback" | "trace";
  status?: "warning";
}
interface GraphViewProps {
  name: string;
  type: "form" | "module" | "macro" | "report";
  /** Default: `/api/graph` (VBA labels). Use `/api/graph-wpf` for suggested WPF names. */
  apiPath?: string;
  graphKind?: "vba" | "wpf";
}

export function GraphView({ name, type, apiPath = "/api/graph", graphKind = "vba" }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<any>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [testReport, setTestReport] = useState<any | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const buildGraph = useCallback(async () => {
    if (!name || !containerRef.current) return;
    setLoading(true);
    setSelectedNode(null);
    setTestReport(null);
    setError(null);

    try {
      const cytoscape = (await import("cytoscape")).default;

      // Register cose-bilkent for force layout
      let layoutName = "cose";
      try {
        const coseBilkent = (await import("cytoscape-cose-bilkent" as any)).default;
        try { (cytoscape as any).use(coseBilkent); } catch { /* already registered */ }
        layoutName = "cose-bilkent";
      } catch {
        // fallback to built-in cose
      }

      const wpfRootCfg =
        graphKind === "wpf"
          ? type === "macro"
            ? TYPE_CFG.handler
            : type === "module"
              ? TYPE_CFG.service
              : TYPE_CFG.view
          : (TYPE_CFG[type] ?? TYPE_CFG.form);

      const res = await fetch(`${apiPath}?name=${encodeURIComponent(name)}&type=${type}`);
      const data = await res.json();
      if (!data.success) { setError(data.error || "Unknown error"); setLoading(false); return; }
      setStats(data.stats);

      // Validate elements to avoid "Invalid array length"
      const nodes: any[] = Array.isArray(data.elements?.nodes) ? data.elements.nodes : [];
      const edges: any[] = Array.isArray(data.elements?.edges) ? data.elements.edges : [];
      if (nodes.length === 0) { setError("Graph is empty — no nodes returned."); setLoading(false); return; }

      const rootId =
        typeof data.rootId === "string" && data.rootId.length > 0
          ? data.rootId
          : `${type}:${name}`;

      const rootCfg = graphKind === "wpf" ? wpfRootCfg : (TYPE_CFG[type] ?? TYPE_CFG["form"]);

      if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; }

      const cy = cytoscape({
        container: containerRef.current,
        elements: [...nodes, ...edges],
        style: [
          // ── Base circular node (all secondary nodes) ──────────────────
          {
            selector: "node",
            style: {
              "shape": "ellipse",
              "width": 28,
              "height": 28,
              "background-color": "#1e2333",
              "border-width": 3,
              "border-color": "var(--border-color)",
              "label": "data(label)",
              "text-valign": "bottom",
              "text-halign": "center",
              "text-margin-y": 5,
              "font-size": 11,
              "font-family": "sans-serif",
              "color": "var(--text-main)",
              "text-wrap": "ellipsis",
              "text-max-width": 100,
              "text-background-color": "var(--bg-dark)",
              "text-background-opacity": 0.8,
              "text-background-padding": "2px",
              "text-background-shape": "roundrectangle",
            } as any,
          },
          // ── Per-type: colored ring + bg ─────────────────────────────────
          ...Object.entries(TYPE_CFG).map(([t, c]) => ({
            selector: `node[type="${t}"]`,
            style: {
              "background-color": c.bg,
              "border-color": c.color,
              "color": c.color,
              "background-opacity": 1,
            } as any,
          })),
          // Event / handler — small
          {
            selector: `node[type="event"], node[type="handler"]`,
            style: {
              "width": 26,
              "height": 26,
            } as any,
          },
          {
            selector: `node[type="view"], node[type="viewmodel"]`,
            style: {
              "width": 45,
              "height": 45,
            } as any,
          },
          // Leaf nodes — smallest
          {
            selector: `node[type="macro"], node[type="module"], node[type="query"], node[type="repository"], node[type="workflow"]`,
            style: {
              "width": 22,
              "height": 22,
            } as any,
          },
          {
            selector: `node[type="warning"], edge[status="warning"]`,
            style: {
              "border-color": "#facc15",
              "line-color": "#facc15",
              "target-arrow-color": "#facc15",
              "color": "#facc15",
              "line-style": "dashed",
            } as any,
          },
          {
            selector: `node.review-error`,
            style: {
              "border-color": "#ef4444",
              "border-width": 7,
              "color": "#fecaca",
              "overlay-color": "#ef4444",
              "overlay-padding": 8,
              "overlay-opacity": 0.16,
              "z-index": 120,
            } as any,
          },
          {
            selector: `edge.review-error`,
            style: {
              "line-color": "#ef4444",
              "target-arrow-color": "#ef4444",
              "width": 4,
              "color": "#fecaca",
              "line-style": "solid",
              "z-index": 119,
            } as any,
          },
          // Selected glow
          {
            selector: "node:selected",
            style: {
              "border-color": "#f59e0b",
              "border-width": 6,
              "color": "#fbbf24",
              "z-index": 100,
              "overlay-color": "#f59e0b",
              "overlay-padding": 6,
              "overlay-opacity": 0.15,
            } as any,
          },
          // Hover
          {
            selector: "node.hover",
            style: {
              "overlay-color": "#ffffff",
              "overlay-padding": 4,
              "overlay-opacity": 0.08,
            } as any,
          },
          // ── Edges ───────────────────────────────────────────────────────
          {
            selector: "edge",
            style: {
              "width": 1.5,
              "line-color": "#2d3748",
              "target-arrow-color": "#4b5563",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "control-point-step-size": 40,
              "arrow-scale": 0.8,
              "label": "data(label)",
              "font-size": 9,
              "color": "var(--text-muted)",
              "text-rotation": "autorotate",
              "text-background-color": "var(--bg-dark)",
              "text-background-opacity": 0.9,
              "text-background-padding": "2px",
              "text-background-shape": "roundrectangle",
            } as any,
          },
          // Highlighted edge (connected to selected node)
          {
            selector: "edge.highlighted",
            style: {
              "line-color": "#f59e0b",
              "target-arrow-color": "#f59e0b",
              "width": 3,
              "z-index": 99,
            } as any,
          },
        ],
        minZoom: 0.1,
        maxZoom: 5,
      });

      // Run layout with fallback to grid on error
      try {
        cy.layout({
          name: layoutName,
          animate: true,
          animationDuration: 500,
          randomize: true,
          idealEdgeLength: 150,
          nodeRepulsion: 8000,
          edgeElasticity: 0.45,
          nestingFactor: 0.1,
          gravity: 0.25,
          numIter: 1500,
          tile: true,
          padding: 40,
          fit: true,
        } as any).run();
      } catch {
        cy.layout({ name: "grid", padding: 40, fit: true } as any).run();
      }

      // ── Style the center node directly (selector approach is unreliable) ──
      const rootNode = cy.getElementById(rootId);
      if (rootNode && rootNode.length > 0) {
        rootNode.style({ "width": 45, "height": 45, "border-width": 5 });
        rootNode.data("isRoot", true);
      }

      cyRef.current = cy;

      // ── Interactions ────────────────────────────────────────────────────
      cy.on("tap", "node", (evt: any) => {
        const nd: NodeData = evt.target.data();
        setSelectedNode(nd);
        cy.elements().removeClass("highlighted");
        evt.target.connectedEdges().addClass("highlighted");
        
        // Pan camera to center on selected node smoothly
        cy.animate({
          center: { eles: evt.target },
          zoom: Math.max(cy.zoom(), 1.1),
          duration: 250
        });
      });
      cy.on("tap", (evt: any) => {
        if (evt.target === cy) {
          setSelectedNode(null);
          cy.elements().removeClass("highlighted");
        }
      });
      cy.on("mouseover", "node", (evt: any) => {
        evt.target.addClass("hover");
        if (containerRef.current) containerRef.current.style.cursor = "pointer";
      });
      cy.on("mouseout", "node", (evt: any) => {
        evt.target.removeClass("hover");
        if (containerRef.current) containerRef.current.style.cursor = "default";
      });

    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [name, type, apiPath, graphKind]);

  const clearReviewHighlights = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("review-error");
  }, []);

  const applySourceReviewHighlights = useCallback((report: any) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("review-error");

    const markNode = (id?: string) => {
      if (!id) return;
      const node = cy.getElementById(id);
      if (node && node.length > 0) node.addClass("review-error");
    };

    const markEdge = (source?: string, target?: string) => {
      if (!source || !target) return;
      markNode(source);
      markNode(target);
      cy.edges().forEach((edge: any) => {
        const data = edge.data();
        if (data.source === source && data.target === target) edge.addClass("review-error");
      });
    };

    for (const err of report?.errors || []) {
      if (Array.isArray(err.expectedNodes)) {
        for (const node of err.expectedNodes) markNode(node.id);
      }
      if (err.expected?.source?.id && err.expected?.target?.id) {
        markEdge(err.expected.source.id, err.expected.target.id);
      }
      if (err.edge?.source && err.edge?.target) {
        markEdge(err.edge.source, err.edge.target);
      }
    }
  }, []);

  const runSourceReview = useCallback(async () => {
    if (!name || graphKind !== "wpf") return;
    setSourceLoading(true);
    setTestReport(null);
    clearReviewHighlights();
    try {
      const exportRes = await fetch(`/api/graph-wpf/export?name=${encodeURIComponent(name)}&type=${type}`, { method: "POST" });
      const exportData = await exportRes.json();
      if (!exportData.success) {
        setTestReport({
          success: false,
          summary: { errors: 1, warnings: 0, nodes: 0, edges: 0 },
          errors: [{ rule: "export", message: exportData.error || "Export expected graph failed" }],
          warnings: [],
        });
        return;
      }

      const res = await fetch(`/api/graph-wpf/source-review?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      const report =
        data.report ?? {
          success: false,
          summary: { errors: 1, warnings: 0, nodes: 0, edges: 0 },
          errors: [{ rule: "source-review", message: data.error || "Unknown error" }],
          warnings: [],
        };
      setTestReport(report);
      if (!report.success) applySourceReviewHighlights(report);
    } catch (e: any) {
      setTestReport({
        success: false,
        summary: { errors: 1, warnings: 0, nodes: 0, edges: 0 },
        errors: [{ rule: "client", message: e.message }],
        warnings: [],
      });
    } finally {
      setSourceLoading(false);
    }
  }, [name, type, graphKind, clearReviewHighlights, applySourceReviewHighlights]);

  useEffect(() => {
    buildGraph();
    return () => { if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; } };
  }, [buildGraph]);

  // Resize canvas when selection drawer toggles
  useEffect(() => {
    if (cyRef.current) {
      const timer = setTimeout(() => {
        if (cyRef.current) cyRef.current.resize();
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [selectedNode]);

  const rootCfg =
    graphKind === "wpf"
      ? type === "macro"
        ? TYPE_CFG.handler
        : type === "module"
          ? TYPE_CFG.service
          : TYPE_CFG.view
      : (TYPE_CFG[type] ?? TYPE_CFG["form"]);

  const legendTypes =
    graphKind === "wpf"
      ? ["view", "viewmodel", "handler", "service", "repository", "navigation", "warning"]
      : ["form", "report", "module", "macro", "query", "event"];

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden", background: "#0d1117" }}>
      {/* ── Main canvas ─────────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>

        {/* Stats strip */}
        {stats && !loading && (
          <div style={{
            position: "absolute", top: 10, left: "50%", transform: "translateX(-50%)",
            zIndex: 20, display: "flex", gap: 6, alignItems: "center",
            background: "rgba(13,17,23,0.9)", border: "1px solid #1f2937",
            borderRadius: 20, padding: "4px 12px",
          }}>
            {(graphKind === "wpf"
              ? [
                  { label: "Views", n: stats.views ?? 0, c: "#22d3ee" },
                  { label: "VM", n: stats.viewmodels ?? 0, c: "#a78bfa" },
                  { label: "Handlers", n: stats.handlers ?? 0, c: "#f472b6" },
                  { label: "Svc", n: stats.services ?? 0, c: "#2dd4bf" },
                  { label: "Repos", n: stats.repositories ?? 0, c: "#4ade80" },
                  { label: "Nav", n: stats.navigation ?? 0, c: "#38bdf8" },
                  { label: "Warn", n: stats.warnings ?? 0, c: "#facc15" },
                ]
              : [
                  { label: "Events",  n: stats.events ?? 0,  c: "#c084fc" },
                  { label: "Macros",  n: stats.macros ?? 0,  c: "#f97316" },
                  { label: "Modules", n: stats.modules ?? 0, c: "#34d399" },
                  { label: "Queries", n: stats.queries ?? 0, c: "#a3e635" },
                  { label: "Forms",   n: stats.forms ?? 0,   c: "#4c9ef8" },
                ]
            ).map((s, i) => (
              <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
                {i > 0 && <span style={{ color: "var(--border-color)" }}>·</span>}
                <span style={{ color: s.c, fontWeight: 700 }}>{s.n}</span>
                <span style={{ color: "var(--text-muted)" }}>{s.label}</span>
              </span>
            ))}
            <span style={{ color: "var(--border-color)", margin: "0 4px" }}>·</span>
            <button onClick={buildGraph} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 13, padding: 0, lineHeight: 1 }} title="Reload">↺</button>
            {graphKind === "wpf" && (
              <>
                <span style={{ color: "var(--border-color)", margin: "0 4px" }}>·</span>
                <button
                  onClick={runSourceReview}
                  disabled={sourceLoading}
                  style={{
                    background: "rgba(168,85,247,0.12)",
                    border: "1px solid #a855f7",
                    color: "#c084fc",
                    cursor: sourceLoading ? "wait" : "pointer",
                    fontSize: 11,
                    fontWeight: 700,
                    borderRadius: 10,
                    padding: "2px 8px",
                    lineHeight: 1.3,
                  }}
                  title="Parse WPF source and diff Expected vs Actual"
                >
                  {sourceLoading ? "Reviewing..." : "Run Source Review"}
                </button>
              </>
            )}
          </div>
        )}

        {graphKind === "wpf" && testReport && !loading && (
          <div style={{
            position: "absolute",
            top: 48,
            right: 12,
            zIndex: 22,
            width: 320,
            maxHeight: 260,
            overflow: "auto",
            background: "rgba(13,17,23,0.96)",
            border: `1px solid ${testReport.success ? "#22c55e" : "#ef4444"}`,
            borderRadius: 10,
            padding: 12,
            boxShadow: "0 12px 30px rgba(0,0,0,0.35)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <span style={{ color: testReport.success ? "#22c55e" : "#ef4444", fontSize: 12, fontWeight: 800 }}>
                WPF Graph Test: {testReport.success ? "PASS" : "FAIL"}
              </span>
              <button onClick={() => setTestReport(null)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14 }}>x</button>
            </div>
            <div style={{ color: "#94a3b8", fontSize: 11, marginBottom: 8 }}>
              {testReport.summary?.errors ?? 0} errors · {testReport.summary?.warnings ?? 0} warnings · {testReport.summary?.nodes ?? 0} nodes · {testReport.summary?.edges ?? 0} edges
            </div>
            {!testReport.success && (
              <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.28)", borderRadius: 6, padding: 8 }}>
                <div style={{ color: "#fecaca", fontSize: 11, lineHeight: 1.4 }}>
                  Các node/đường màu đỏ trên graph là flow expected đang thiếu hoặc sai trong source.
                </div>
                <div style={{ color: "#94a3b8", fontSize: 10, marginTop: 6 }}>
                  Click node đỏ để xem id/type. Text report chi tiết vẫn nằm trong response API khi cần debug sâu.
                </div>
              </div>
            )}
            {testReport.success && (testReport.warnings || []).length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {(testReport.warnings || []).slice(0, 4).map((warn: any, idx: number) => (
                  <div key={`${warn.rule}-${idx}`} style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.28)", borderRadius: 6, padding: 8 }}>
                    <div style={{ color: "#86efac", fontSize: 10, fontWeight: 800 }}>{warn.rule}</div>
                    <div style={{ color: "var(--text-main)", fontSize: 11, lineHeight: 1.35 }}>{warn.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", zIndex: 30, background: "#0d1117" }}>
            <div style={{ position: "relative", width: 64, height: 64, marginBottom: 16 }}>
              <div style={{ width: 64, height: 64, borderRadius: "50%", border: `4px solid ${rootCfg.ring}33`, borderTopColor: rootCfg.ring, animation: "spin 0.9s linear infinite" }} />
              <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>{rootCfg.icon}</span>
            </div>
            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
              Loading {graphKind === "wpf" ? "WPF " : ""}graph for <strong style={{ color: "var(--text-muted)" }}>{name}</strong>…
            </span>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
            <span style={{ fontSize: 36 }}>⚠️</span>
            <span style={{ color: "#ef4444", fontSize: 13 }}>{error}</span>
            <button onClick={buildGraph} style={{ padding: "6px 18px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid #ef4444", color: "#ef4444", cursor: "pointer", fontSize: 12 }}>Retry</button>
          </div>
        )}

        {/* Legend */}
        <div style={{ position: "absolute", bottom: 12, left: 12, zIndex: 20, background: "rgba(13,17,23,0.92)", border: "1px solid #1f2937", borderRadius: 10, padding: "10px 14px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 14px" }}>
            {legendTypes.map((t) => {
              const c = TYPE_CFG[t];
              if (!c) return null;
              return (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 12, height: 12, borderRadius: "50%", background: c.bg, border: `2px solid ${c.color}` }} />
                  <span style={{ fontSize: 10, color: c.color, fontWeight: 600 }}>{c.abbr}</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "capitalize" }}>{t}</span>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 6, fontSize: 9, color: "var(--border-color)" }}>
            {graphKind === "wpf" && (
              <div style={{ marginBottom: 4, color: "#22d3ee", fontWeight: 600 }}>
                WPF Expected: View → ViewModel → Command → Service → Repository
              </div>
            )}
            Scroll zoom · Drag pan · Click select
          </div>
        </div>

        {/* Canvas */}
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      </div>

      {/* ── Detail panel (slides in on node select) ─────────────────────── */}
      <div style={{
        width: selectedNode ? 240 : 0,
        overflow: "hidden",
        transition: "width 0.22s cubic-bezier(.4,0,.2,1)",
        borderLeft: selectedNode ? "1px solid #1f2937" : "none",
        background: "#10131c",
        flexShrink: 0,
      }}>
        {selectedNode && (() => {
          const nc = TYPE_CFG[selectedNode.type] ?? TYPE_CFG["form"];
          const isRoot = (selectedNode as any).isRoot === true;

          const dependencies: { relation: string; targetLabel: string; targetType: string; direction: 'out' | 'in' }[] = [];
          if (cyRef.current) {
            const nodeEl = cyRef.current.getElementById(selectedNode.id);
            if (nodeEl.length > 0) {
              nodeEl.outgoers('edge').forEach((edge: any) => {
                const edgeData = edge.data();
                const targetNode = edge.target();
                if (targetNode.length > 0) {
                  dependencies.push({
                    relation: edgeData.label || 'references',
                    targetLabel: targetNode.data('label') || targetNode.data('id'),
                    targetType: targetNode.data('type') || 'unknown',
                    direction: 'out'
                  });
                }
              });
              nodeEl.incomers('edge').forEach((edge: any) => {
                const edgeData = edge.data();
                const sourceNode = edge.source();
                if (sourceNode.length > 0) {
                  dependencies.push({
                    relation: edgeData.label || 'referenced by',
                    targetLabel: sourceNode.data('label') || sourceNode.data('id'),
                    targetType: sourceNode.data('type') || 'unknown',
                    direction: 'in'
                  });
                }
              });
            }
          }

          return (
            <div style={{ padding: 16, width: 240 }}>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                {/* Node icon — double ring if center node */}
                <div style={{
                  width: 44, height: 44, borderRadius: "50%",
                  background: nc.bg,
                  border: `3px solid ${nc.color}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 20, flexShrink: 0,
                  boxShadow: isRoot
                    ? `0 0 0 4px ${nc.color}55, 0 0 0 8px ${nc.color}22, 0 0 16px ${nc.color}66`
                    : "none",
                }}>
                  {nc.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 9, color: nc.color, fontWeight: 700, letterSpacing: "0.1em", marginBottom: 2 }}>{nc.abbr}</div>
                  <div style={{ fontSize: 12, color: "var(--text-main)", fontWeight: 600, wordBreak: "break-all", lineHeight: 1.3 }}>{selectedNode.label}</div>
                </div>
                <button onClick={() => setSelectedNode(null)} style={{ background: "none", border: "none", color: "#4b5563", cursor: "pointer", fontSize: 16, lineHeight: 1, flexShrink: 0 }}>×</button>
              </div>

              {/* CENTER NODE badge */}
              {isRoot && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                  background: `${nc.color}18`,
                  border: `1px solid ${nc.color}`,
                  borderRadius: 8, padding: "7px 10px", marginBottom: 8,
                }}>
                  <span style={{ fontSize: 14 }}>⭐</span>
                  <span style={{ fontSize: 11, color: nc.color, fontWeight: 700, letterSpacing: "0.06em" }}>CENTER NODE</span>
                </div>
              )}

              {/* Properties */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {/* Relationships list */}
                {dependencies.length > 0 && (
                  <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 9, color: "#a78bfa", fontWeight: 700, marginBottom: 5 }}>RELATIONSHIPS ({dependencies.length})</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 180, overflowY: "auto", paddingRight: 4 }} className="custom-scrollbar">
                      {dependencies.map((dep, index) => {
                        const targetColor = TYPE_CFG[dep.targetType]?.color || "#94a3b8";
                        return (
                          <div key={index} style={{ display: "flex", flexDirection: "column", borderBottom: index < dependencies.length - 1 ? "1px solid #30363d" : "none", paddingBottom: 4, gap: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <span style={{ fontSize: 8, padding: "1px 4px", borderRadius: 3, background: dep.direction === "out" ? "rgba(59,130,246,0.15)" : "rgba(16,185,129,0.15)", color: dep.direction === "out" ? "#3b82f6" : "#10b981", fontWeight: 800 }}>
                                {dep.direction === "out" ? "OUT" : "IN"}
                              </span>
                              <span style={{ fontSize: 9, color: "#8b949e", textTransform: "uppercase", fontWeight: 700 }}>
                                {dep.relation}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: targetColor, fontWeight: 600, wordBreak: "break-all" }}>
                              {dep.targetLabel}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {selectedNode.badge && (
                  <div style={{ background: `${nc.color}18`, border: `1px solid ${nc.color}44`, borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 9, color: nc.color, fontWeight: 700, marginBottom: 3 }}>SUMMARY</div>
                    <div style={{ fontSize: 12, color: nc.color }}>{selectedNode.badge}</div>
                  </div>
                )}
                {selectedNode.vbaLabel && selectedNode.vbaLabel !== selectedNode.label && (
                  <div style={{ background: "#1a1d2e", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 9, color: "#22d3ee", fontWeight: 700, marginBottom: 3 }}>VBA (Access)</div>
                    <div style={{ fontSize: 11, color: "#94a3b8", wordBreak: "break-all", lineHeight: 1.35 }}>{selectedNode.vbaLabel}</div>
                  </div>
                )}
                {selectedNode.mappingStatus && (
                  <div style={{ background: "#1a1d2e", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, marginBottom: 3 }}>MAPPING</div>
                    <span style={{ fontSize: 11, color: selectedNode.mappingStatus === "mapped" ? "#4ade80" : "#facc15", fontWeight: 700 }}>
                      {selectedNode.mappingStatus}
                    </span>
                  </div>
                )}
                <div style={{ background: "#1a1d2e", borderRadius: 8, padding: "8px 10px" }}>
                  <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, marginBottom: 3 }}>NODE TYPE</div>
                  <span style={{ fontSize: 11, background: `${nc.color}22`, border: `1px solid ${nc.color}55`, color: nc.color, padding: "2px 8px", borderRadius: 4, fontWeight: 600 }}>{nc.abbr}</span>
                </div>
                <div style={{ background: "#1a1d2e", borderRadius: 8, padding: "8px 10px" }}>
                  <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, marginBottom: 3 }}>ID</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", wordBreak: "break-all", fontFamily: "monospace", lineHeight: 1.5 }}>{selectedNode.id}</div>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
