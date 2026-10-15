import React, { useState, useMemo } from "react";
import type { SubgraphResponse, GraphNode } from "../../types/investigation";
import { Layers } from "lucide-react";

interface GraphCanvasProps {
  data: SubgraphResponse | null;
  targetNodeId?: string;
  disappearedNodeIds?: string[];
  disappearedEdgeIds?: string[];
  isLoading?: boolean;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  targetNodeId,
  disappearedNodeIds = [],
  disappearedEdgeIds = [],
  isLoading = false,
}) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Compute 2D node layout positions in an interactive circular / force layout
  const layout = useMemo(() => {
    if (!data || data.nodes.length === 0) return { nodes: [], edges: [], width: 700, height: 450 };

    const width = 760;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;

    const positions: Record<string, { x: number; y: number }> = {};


    // If targetNodeId exists, place at center
    if (targetNodeId) {
      positions[targetNodeId] = { x: centerX, y: centerY };
    }

    const otherNodes = data.nodes.filter((n) => n.id !== targetNodeId);
    const radius = Math.min(width, height) * 0.38;

    otherNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(1, otherNodes.length)) * 2 * Math.PI;
      const jitter = (idx % 2 === 0 ? 1 : 0.82);
      positions[node.id] = {
        x: centerX + radius * jitter * Math.cos(angle),
        y: centerY + radius * jitter * Math.sin(angle),
      };
    });

    return {
      nodes: data.nodes.map((n) => ({
        ...n,
        x: positions[n.id]?.x ?? centerX,
        y: positions[n.id]?.y ?? centerY,
      })),
      edges: data.edges,
      width,
      height,
    };
  }, [data, targetNodeId]);

  if (isLoading) {
    return (
      <div
        style={{
          height: "440px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-muted)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <Layers size={32} style={{ animation: "spin 2s linear infinite", marginBottom: "0.5rem", color: "var(--accent-blue)" }} />
          <p style={{ fontSize: "0.85rem" }}>Querying FalkorDB topology...</p>
        </div>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div
        style={{
          height: "440px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-muted)",
          padding: "2rem",
          textAlign: "center",
        }}
      >
        <div>
          <Layers size={36} color="var(--border-strong)" style={{ marginBottom: "0.75rem" }} />
          <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", fontWeight: 500 }}>
            No graph nodes selected
          </p>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
            Select a module or run an investigation above to render the live dependency graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: "#ffffff",
        borderRadius: "8px",
        border: "1px solid var(--border-subtle)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Legend & Stats Banner */}
      <div
        style={{
          padding: "0.6rem 1rem",
          backgroundColor: "var(--bg-muted)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "0.78rem",
          color: "var(--text-secondary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "var(--accent-blue)" }} />
            Target Module
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#64748b" }} />
            Connected Module
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "16px", height: "2px", backgroundColor: "#3b82f6" }} />
            DEPENDS_ON
          </span>
          {disappearedEdgeIds.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.35rem", color: "#e11d48" }}>
              <span style={{ width: "16px", height: "2px", backgroundColor: "#e11d48", borderTop: "2px dashed #e11d48" }} />
              Disrupted in Simulation
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: "0.75rem", fontWeight: 600 }}>
          <span>{layout.nodes.length} Nodes</span>
          <span>{layout.edges.length} Edges</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        style={{ width: "100%", height: "420px", display: "block", userSelect: "none" }}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="22"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#94a3b8" />
          </marker>
          <marker
            id="arrow-broken"
            viewBox="0 0 10 10"
            refX="22"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#e11d48" />
          </marker>
        </defs>

        {/* Edges */}
        {layout.edges.map((edge) => {
          const src = layout.nodes.find((n) => n.id === edge.source);
          const dst = layout.nodes.find((n) => n.id === edge.target);
          if (!src || !dst) return null;

          const isDisrupted = disappearedEdgeIds.includes(edge.id);
          const isRelatedToHover = hoveredNode === edge.source || hoveredNode === edge.target;

          return (
            <g key={edge.id}>
              <line
                x1={src.x}
                y1={src.y}
                x2={dst.x}
                y2={dst.y}
                stroke={isDisrupted ? "#e11d48" : isRelatedToHover ? "#2563eb" : "#cbd5e1"}
                strokeWidth={isDisrupted ? 2 : isRelatedToHover ? 2.5 : 1.5}
                strokeDasharray={isDisrupted ? "4,4" : undefined}
                markerEnd={isDisrupted ? "url(#arrow-broken)" : "url(#arrow)"}
              />
            </g>
          );
        })}

        {/* Nodes */}
        {layout.nodes.map((node) => {
          const isTarget = node.id === targetNodeId;
          const isDisrupted = disappearedNodeIds.includes(node.id);
          const isSelected = selectedNode?.id === node.id;
          const isHovered = hoveredNode === node.id;

          const fill = isTarget
            ? "#2563eb"
            : isDisrupted
            ? "#e11d48"
            : "#ffffff";
          const stroke = isTarget
            ? "#1d4ed8"
            : isDisrupted
            ? "#be123c"
            : isSelected || isHovered
            ? "#2563eb"
            : "#94a3b8";

          const shortLabel = node.label.length > 22 ? `${node.label.slice(0, 20)}...` : node.label;

          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => setSelectedNode(node)}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              style={{ cursor: "pointer" }}
            >
              {isTarget && (
                <circle r={26} fill="rgba(37, 99, 235, 0.15)" stroke="rgba(37, 99, 235, 0.4)" strokeWidth={1} />
              )}
              <circle
                r={isTarget ? 18 : 14}
                fill={fill}
                stroke={stroke}
                strokeWidth={isSelected || isTarget ? 3 : 2}
              />
              <text
                dy={isTarget ? 30 : 25}
                textAnchor="middle"
                fontSize={isTarget ? "11px" : "10px"}
                fontWeight={isTarget ? 700 : 500}
                fill={isTarget ? "#0f172a" : "#475569"}
              >
                {shortLabel}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div
          style={{
            position: "absolute",
            bottom: "0.75rem",
            left: "0.75rem",
            right: "0.75rem",
            backgroundColor: "rgba(255, 255, 255, 0.96)",
            backdropFilter: "blur(4px)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "6px",
            padding: "0.6rem 0.85rem",
            fontSize: "0.78rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{selectedNode.label}</span>
            <span style={{ marginLeft: "0.5rem", color: "var(--text-muted)" }}>({selectedNode.id})</span>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            style={{
              border: "none",
              background: "transparent",
              color: "var(--text-muted)",
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
};
