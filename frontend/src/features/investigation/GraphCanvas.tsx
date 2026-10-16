/**
 * GraphCanvas — Dependency graph renderer with deterministic hierarchical lane layout.
 *
 * Layout strategy:
 *   - Target node is placed in the center column (lane 0).
 *   - Nodes are bucketed by their shortest hop-distance to/from target:
 *     outgoing deps (target depends on them) → right lanes (+1, +2, …)
 *     incoming dependents (they depend on target) → left lanes (-1, -2, …)
 *   - Within each lane, nodes are distributed vertically with uniform spacing.
 *   - Same input → same layout (deterministic: sorted by stable node ID).
 *
 * Visual semantics:
 *   ● Blue filled = target module
 *   ● White/blue-ring = incoming dependent (depends on target)
 *   ● White/slate-ring = outgoing dependency (target depends on it)
 *   ● Red dashed = path disrupted in counterfactual scenario
 *   ● Green outline = surviving path in counterfactual scenario
 *   → arrows always point in DEPENDS_ON direction (from dependent → dependency)
 */

import React, { useState, useMemo } from "react";
import type { SubgraphResponse, GraphNode } from "../../types/investigation";
import { Layers } from "lucide-react";

interface LayoutNode extends GraphNode {
  x: number;
  y: number;
  lane: number;
  role: "target" | "dependent" | "dependency" | "unknown";
}

interface GraphCanvasProps {
  data: SubgraphResponse | null;
  targetNodeId?: string;
  disappearedNodeIds?: string[];
  disappearedEdgeIds?: string[];
  survivingNodeIds?: string[];
  isLoading?: boolean;
}

/** Assign DEPENDS_ON roles: who is a dependent (caller) vs dependency (callee) of target? */
function computeRoles(
  nodes: GraphNode[],
  edges: SubgraphResponse["edges"],
  targetId: string
): Record<string, "target" | "dependent" | "dependency" | "unknown"> {
  const roles: Record<string, "target" | "dependent" | "dependency" | "unknown"> = {};
  for (const n of nodes) roles[n.id] = "unknown";
  roles[targetId] = "target";

  // Nodes that point TO target → dependents (upstream callers)
  // Edge direction: source -[:DEPENDS_ON]-> target
  for (const e of edges) {
    if (e.target === targetId) roles[e.source] = "dependent";
    if (e.source === targetId) roles[e.target] = "dependency";
  }
  return roles;
}

/** BFS lane assignment: 0=target, -N=dependents, +N=dependencies */
function assignLanes(
  nodes: GraphNode[],
  edges: SubgraphResponse["edges"],
  targetId: string
): Record<string, number> {
  const lanes: Record<string, number> = { [targetId]: 0 };
  const queue: string[] = [targetId];

  // Build adjacency: forward (dependency) and reverse (dependent)
  const fwd: Record<string, string[]> = {};
  const rev: Record<string, string[]> = {};
  for (const e of edges) {
    (fwd[e.source] ||= []).push(e.target);
    (rev[e.target] ||= []).push(e.source);
  }

  while (queue.length > 0) {
    const cur = queue.shift()!;
    const curLane = lanes[cur];

    // Dependencies are one lane to the RIGHT (+1)
    for (const dep of fwd[cur] || []) {
      if (!(dep in lanes)) {
        lanes[dep] = curLane + 1;
        queue.push(dep);
      }
    }
    // Dependents are one lane to the LEFT (-1)
    for (const dep of rev[cur] || []) {
      if (!(dep in lanes)) {
        lanes[dep] = curLane - 1;
        queue.push(dep);
      }
    }
  }
  // Any unreached node goes in lane 0 (fallback)
  for (const n of nodes) {
    if (!(n.id in lanes)) lanes[n.id] = 0;
  }
  return lanes;
}

const LANE_WIDTH = 170;   // px between lane centers
const NODE_V_SPACING = 68; // px between nodes in same lane
const MAX_VISIBLE_NODES = 40;

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  targetNodeId,
  disappearedNodeIds = [],
  disappearedEdgeIds = [],
  survivingNodeIds = [],
  isLoading = false,
}) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const layout = useMemo((): {
    nodes: LayoutNode[];
    edges: SubgraphResponse["edges"];
    width: number;
    height: number;
    truncated: boolean;
  } => {
    if (!data || data.nodes.length === 0) {
      return { nodes: [], edges: [], width: 700, height: 450, truncated: false };
    }

    const rawVisibleNodes = showAll ? data.nodes : data.nodes.slice(0, MAX_VISIBLE_NODES);
    // Deduplicate nodes by ID to enforce UI key integrity and stable coordinates
    const visibleNodes = Array.from(new Map(rawVisibleNodes.map((n) => [n.id, n])).values());
    const truncated = !showAll && data.nodes.length > MAX_VISIBLE_NODES;
    const tid = targetNodeId || visibleNodes[0]?.id;

    const lanes = assignLanes(visibleNodes, data.edges, tid);
    const roles = computeRoles(visibleNodes, data.edges, tid);

    // Group by lane
    const byLane: Record<number, GraphNode[]> = {};
    for (const n of visibleNodes) {
      const l = lanes[n.id] ?? 0;
      (byLane[l] ||= []).push(n);
    }

    // Sort each lane by stable ID for determinism
    for (const l in byLane) {
      byLane[l].sort((a, b) => (a.id > b.id ? 1 : -1));
    }

    const laneKeys = Object.keys(byLane).map(Number).sort((a, b) => a - b);
    const minLane = laneKeys[0] ?? 0;
    const maxLane = laneKeys[laneKeys.length - 1] ?? 0;
    const laneCount = maxLane - minLane + 1;

    const canvasWidth = Math.max(700, laneCount * LANE_WIDTH + 120);
    const maxNodesInLane = Math.max(...Object.values(byLane).map((ns) => ns.length), 1);
    const canvasHeight = Math.max(420, maxNodesInLane * NODE_V_SPACING + 120);

    const centerX = canvasWidth / 2;
    const centerY = canvasHeight / 2;

    const positions: Record<string, { x: number; y: number }> = {};

    for (const laneNum of laneKeys) {
      const laneNodes = byLane[laneNum];
      const laneX = centerX + (laneNum - 0) * LANE_WIDTH;
      const totalHeight = (laneNodes.length - 1) * NODE_V_SPACING;
      laneNodes.forEach((n, idx) => {
        const laneY = centerY - totalHeight / 2 + idx * NODE_V_SPACING;
        positions[n.id] = { x: laneX, y: laneY };
      });
    }

    // Filter edges: only include edges between visible nodes and deduplicate
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    const seenEdges = new Set<string>();
    const visibleEdges = data.edges.filter((e) => {
      if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) return false;
      const edgeKey = `${e.source}->${e.target}:${e.id || e.label}`;
      if (seenEdges.has(edgeKey)) return false;
      seenEdges.add(edgeKey);
      return true;
    });

    return {
      nodes: visibleNodes.map((n) => ({
        ...n,
        x: positions[n.id]?.x ?? centerX,
        y: positions[n.id]?.y ?? centerY,
        lane: lanes[n.id] ?? 0,
        role: roles[n.id] ?? "unknown",
      })),
      edges: visibleEdges,
      width: canvasWidth,
      height: canvasHeight,
      truncated,
    };
  }, [data, targetNodeId, showAll]);

  if (isLoading) {
    return (
      <div style={loadingStyle}>
        <div style={{ textAlign: "center" }}>
          <Layers
            size={32}
            style={{ animation: "spin 2s linear infinite", marginBottom: "0.5rem", color: "var(--accent-blue)" }}
          />
          <p style={{ fontSize: "0.85rem" }}>Querying FalkorDB topology...</p>
        </div>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div style={{ ...loadingStyle, flexDirection: "column", gap: "0.5rem" }}>
        <Layers size={36} color="var(--border-strong)" />
        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", fontWeight: 500 }}>No graph nodes selected</p>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Select a module or run an investigation to render the live dependency graph.
        </p>
      </div>
    );
  }

  const { nodes, edges, width, height, truncated } = layout;

  return (
    <div style={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid var(--border-subtle)", overflow: "hidden", position: "relative" }}>
      {/* ── Legend & Stats ── */}
      <div style={legendBarStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <LegendDot color="#2563eb" label="Target" />
          <LegendDot color="transparent" stroke="#64748b" label="Dep. on target (upstream)" />
          <LegendDot color="transparent" stroke="#0891b2" label="Target's dependency" />
          {disappearedEdgeIds.length > 0 && <LegendLine color="#e11d48" dashed label="Disrupted (scenario)" />}
          {survivingNodeIds.length > 0 && <LegendDot color="transparent" stroke="#16a34a" label="Surviving path" />}
          <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>→ arrows = DEPENDS_ON direction</span>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", fontWeight: 600, fontSize: "0.78rem" }}>
          <span>{data.nodes.length} Nodes</span>
          <span>{data.edges.length} Edges</span>
          {truncated && (
            <span style={{ color: "#d97706" }}>
              (showing {MAX_VISIBLE_NODES}/{data.nodes.length})
            </span>
          )}
        </div>
      </div>

      {/* ── SVG Canvas ── */}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", height: "430px", display: "block", userSelect: "none" }}
      >
        <defs>
          <marker id="arrow-normal" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#94a3b8" />
          </marker>
          <marker id="arrow-broken" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#e11d48" />
          </marker>
          <marker id="arrow-hover" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#2563eb" />
          </marker>
          <marker id="arrow-surviving" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#16a34a" />
          </marker>
        </defs>

        {/* ── Lane dividers (subtle vertical guides) ── */}
        {Array.from(new Set(nodes.map((n) => Math.round(n.x)))).map((laneX) => (
          <line
            key={`guide-${laneX}`}
            x1={laneX}
            y1={24}
            x2={laneX}
            y2={height - 24}
            stroke="#f1f5f9"
            strokeWidth={1}
          />
        ))}

        {/* ── Edges ── */}
        {edges.map((edge) => {
          const src = nodes.find((n) => n.id === edge.source);
          const dst = nodes.find((n) => n.id === edge.target);
          if (!src || !dst) return null;

          const isDisrupted = disappearedEdgeIds.includes(edge.id) || disappearedNodeIds.includes(edge.source) || disappearedNodeIds.includes(edge.target);
          const isSurviving = survivingNodeIds.includes(edge.source) || survivingNodeIds.includes(edge.target);
          const isRelatedToHover = hoveredNode === edge.source || hoveredNode === edge.target;

          let stroke = "#cbd5e1";
          let strokeWidth = 1.5;
          let dashed: string | undefined;
          let marker = "url(#arrow-normal)";

          if (isDisrupted) {
            stroke = "#e11d48"; strokeWidth = 2; dashed = "5,4"; marker = "url(#arrow-broken)";
          } else if (isRelatedToHover) {
            stroke = "#2563eb"; strokeWidth = 2.5; marker = "url(#arrow-hover)";
          } else if (isSurviving) {
            stroke = "#16a34a"; strokeWidth = 2; marker = "url(#arrow-surviving)";
          }

          // Offset line endpoints to avoid overlap with node circles
          const nodeR = 15;
          const dx = dst.x - src.x;
          const dy = dst.y - src.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const x1 = src.x + (dx / dist) * (nodeR + 2);
          const y1 = src.y + (dy / dist) * (nodeR + 2);
          const x2 = dst.x - (dx / dist) * (nodeR + 2);
          const y2 = dst.y - (dy / dist) * (nodeR + 2);

          return (
            <line
              key={`${edge.source}->${edge.target}-${edge.id}`}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={stroke}
              strokeWidth={strokeWidth}
              strokeDasharray={dashed}
              markerEnd={marker}
              opacity={isDisrupted ? 1 : isSurviving ? 0.9 : 0.75}
            />
          );
        })}

        {/* ── Nodes ── */}
        {nodes.map((node) => {
          const isTarget = node.id === targetNodeId;
          const isDisrupted = disappearedNodeIds.includes(node.id);
          const isSurviving = !isTarget && survivingNodeIds.includes(node.id);
          const isSelected = selectedNode?.id === node.id;
          const isHovered = hoveredNode === node.id;
          const isDep = node.role === "dependency";
          const isUpstream = node.role === "dependent";

          let fill = "#ffffff";
          let stroke = "#94a3b8";
          let strokeWidth = 1.5;
          let r = 15;

          if (isTarget) {
            fill = "#2563eb"; stroke = "#1d4ed8"; strokeWidth = 3; r = 20;
          } else if (isDisrupted) {
            fill = "#fee2e2"; stroke = "#e11d48"; strokeWidth = 2.5;
          } else if (isSurviving) {
            fill = "#f0fdf4"; stroke = "#16a34a"; strokeWidth = 2.5;
          } else if (isSelected || isHovered) {
            stroke = "#2563eb"; strokeWidth = 2.5;
          } else if (isUpstream) {
            stroke = "#64748b"; strokeWidth = 2;
          } else if (isDep) {
            stroke = "#0891b2"; strokeWidth = 2;
          }

          // Smart label truncation based on available horizontal space
          const rawLabel = node.label || node.id;
          const maxChars = isTarget ? 18 : 14;
          const shortLabel = rawLabel.length > maxChars ? `${rawLabel.slice(0, maxChars - 1)}…` : rawLabel;

          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => setSelectedNode(selectedNode?.id === node.id ? null : node)}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              style={{ cursor: "pointer" }}
            >
              {/* Glow ring for target */}
              {isTarget && (
                <circle r={r + 9} fill="rgba(37,99,235,0.12)" stroke="rgba(37,99,235,0.3)" strokeWidth={1} />
              )}
              {/* Role indicator ring */}
              {isSelected && (
                <circle r={r + 5} fill="none" stroke="#2563eb" strokeWidth={1.5} strokeDasharray="3,2" />
              )}
              <circle
                r={r}
                fill={fill}
                stroke={stroke}
                strokeWidth={strokeWidth}
              />
              {/* Label below node */}
              <text
                dy={r + 14}
                textAnchor="middle"
                fontSize={isTarget ? "11px" : "10px"}
                fontWeight={isTarget ? 700 : 500}
                fill={isTarget ? "#0f172a" : isDisrupted ? "#9f1239" : isSurviving ? "#15803d" : "#475569"}
              >
                {shortLabel}
              </text>
              {/* Role badge */}
              {!isTarget && (
                <text
                  dy={r + 25}
                  textAnchor="middle"
                  fontSize="8.5px"
                  fill={isUpstream ? "#64748b" : isDep ? "#0891b2" : "#94a3b8"}
                >
                  {isUpstream ? "▲ upstream" : isDep ? "▼ dep" : ""}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* ── Truncation Notice ── */}
      {truncated && (
        <div style={{ padding: "0.4rem 1rem", backgroundColor: "#fef3c7", borderTop: "1px solid #fcd34d", fontSize: "0.78rem", color: "#92400e", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Showing {MAX_VISIBLE_NODES} of {data.nodes.length} nodes. Results are bounded.</span>
          <button
            onClick={() => setShowAll(true)}
            style={{ background: "none", border: "1px solid #d97706", borderRadius: "4px", padding: "2px 8px", cursor: "pointer", color: "#92400e", fontSize: "0.75rem" }}
          >
            Show all
          </button>
        </div>
      )}

      {/* ── Selected Node Details ── */}
      {selectedNode && (
        <div style={nodeDetailStyle}>
          <div>
            <span style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.82rem" }}>{selectedNode.label}</span>
            <br />
            <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>ID: {selectedNode.id}</span>
            {selectedNode.type && (
              <span style={{ marginLeft: "0.75rem", color: "var(--text-muted)", fontSize: "0.72rem" }}>Type: {selectedNode.type}</span>
            )}
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            style={{ border: "none", background: "transparent", color: "var(--text-muted)", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
};

// ── Sub-components ─────────────────────────────────────────────────────────────

const LegendDot: React.FC<{ color: string; stroke?: string; label: string }> = ({ color, stroke, label }) => (
  <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
    <span style={{
      width: "10px", height: "10px", borderRadius: "50%",
      backgroundColor: color, border: stroke ? `2px solid ${stroke}` : "none",
      flexShrink: 0,
    }} />
    <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>{label}</span>
  </span>
);

const LegendLine: React.FC<{ color: string; dashed?: boolean; label: string }> = ({ color, dashed, label }) => (
  <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
    <span style={{
      width: "18px", height: "2px",
      background: dashed ? "none" : color,
      borderTop: dashed ? `2px dashed ${color}` : "none",
      flexShrink: 0,
    }} />
    <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>{label}</span>
  </span>
);

// ── Styles ─────────────────────────────────────────────────────────────────────

const loadingStyle: React.CSSProperties = {
  height: "440px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#ffffff",
  borderRadius: "8px",
  border: "1px solid var(--border-subtle)",
  color: "var(--text-muted)",
};

const legendBarStyle: React.CSSProperties = {
  padding: "0.55rem 1rem",
  backgroundColor: "var(--bg-muted)",
  borderBottom: "1px solid var(--border-subtle)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: "0.78rem",
  color: "var(--text-secondary)",
  flexWrap: "wrap",
  gap: "0.5rem",
};

const nodeDetailStyle: React.CSSProperties = {
  position: "absolute",
  bottom: "0.75rem",
  left: "0.75rem",
  right: "0.75rem",
  backgroundColor: "rgba(255,255,255,0.97)",
  backdropFilter: "blur(4px)",
  border: "1px solid var(--border-subtle)",
  borderRadius: "6px",
  padding: "0.6rem 0.85rem",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
};
