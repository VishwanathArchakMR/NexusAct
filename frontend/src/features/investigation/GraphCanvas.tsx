/**
 * GraphCanvas — Premium interactive dependency graph explorer for NexusAct.
 *
 * Architecture & Features:
 *   - Deterministic hierarchical lane layout preserving canonical DEPENDS_ON semantics:
 *       Upstream callers (dependents) -> Left lanes (-1, -2)
 *       Target module in central focus -> Center lane (0)
 *       Downstream dependencies (callees) -> Right lanes (+1, +2)
 *       Directed arrows point in DEPENDS_ON direction (caller -> callee)
 *   - Viewport controls: Pan (drag background), Zoom (wheel / +/- buttons), Fit-to-view, Reset.
 *   - Bounded exploration: Search filter, hop depth controls (1-hop, 2-hops, All), node-type filters.
 *   - Contextual inspection panel: Selected node details, in/out degrees, and selected edge evidence.
 *   - Multi-hop path tracing: Highlights connected paths (e.g. A -> B -> C -> D) with glowing strokes.
 *   - Counterfactual scenario diffing: Disrupted paths (red dashed) and surviving paths (green).
 *   - Light & Dark theme support with contrast-aware tokens.
 */

import React, { useState, useMemo, useRef, useCallback, useEffect } from "react";
import type { SubgraphResponse, GraphNode, GraphEdge } from "../../types/investigation";
import {
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Search,
  Filter,
  X,
  ArrowRight,
  Info,
  Compass,
  FileCode,
} from "lucide-react";


export interface LayoutNode extends GraphNode {
  x: number;
  y: number;
  lane: number;
  role: "target" | "dependent" | "dependency" | "path" | "isolated";
  inDegree: number;
  outDegree: number;
}

export interface GraphCanvasProps {
  data: SubgraphResponse | null;
  targetNodeId?: string;
  disappearedNodeIds?: string[];
  disappearedEdgeIds?: string[];
  survivingNodeIds?: string[];
  highlightPathNodes?: string[];
  isLoading?: boolean;
  onSelectTarget?: (nodeId: string) => void;
  onOpenSourceFile?: (filePath: string) => void;
}

// Layout parameters
const LANE_WIDTH = 240;
const NODE_RADIUS_DEFAULT = 16;
const NODE_RADIUS_TARGET = 22;
const MAX_NODES_PER_LANE = 12;

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  targetNodeId,
  disappearedNodeIds = [],
  disappearedEdgeIds = [],
  survivingNodeIds = [],
  highlightPathNodes = [],
  isLoading = false,
  onSelectTarget,
  onOpenSourceFile,
}) => {
  // View mode: Investigation Path vs Network Overview
  const [graphViewMode, setGraphViewMode] = useState<"path" | "overview">("path");

  // Viewport transforms (Pan & Zoom)
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);

  const [startPan, setStartPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Interactive selection & filtering
  const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [hopDepth, setHopDepth] = useState<1 | 2 | 3>(2);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("ALL");

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const [prevTarget, setPrevTarget] = useState<string | undefined>(targetNodeId);
  if (targetNodeId !== prevTarget) {
    setPrevTarget(targetNodeId);
    setPan({ x: 0, y: 0 });
    setZoom(1.0);
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  // Compute Layout & Coordinates
  const layout = useMemo((): {
    nodes: LayoutNode[];
    edges: GraphEdge[];
    width: number;
    height: number;
    totalAvailableNodes: number;
    totalAvailableEdges: number;
  } => {
    if (!data || data.nodes.length === 0) {
      return {
        nodes: [],
        edges: [],
        width: 850,
        height: 520,
        totalAvailableNodes: 0,
        totalAvailableEdges: 0,
      };
    }

    const totalAvailableNodes = data.total_nodes || data.nodes.length;
    const totalAvailableEdges = data.total_edges || data.edges.length;

    // Deduplicate input nodes
    const nodeMap = new Map<string, GraphNode>();
    for (const n of data.nodes) {
      if (!nodeMap.has(n.id)) nodeMap.set(n.id, n);
    }
    const allUniqueNodes = Array.from(nodeMap.values());

    // Resolve active central target
    const tid =
      targetNodeId && nodeMap.has(targetNodeId)
        ? targetNodeId
        : allUniqueNodes[0]?.id || "";

    // Build degree maps & adjacency
    const fwdAdj = new Map<string, Set<string>>(); // source -> targets (dependencies)
    const revAdj = new Map<string, Set<string>>(); // target -> sources (dependents)
    const inDegrees = new Map<string, number>();
    const outDegrees = new Map<string, number>();

    for (const n of allUniqueNodes) {
      fwdAdj.set(n.id, new Set());
      revAdj.set(n.id, new Set());
      inDegrees.set(n.id, 0);
      outDegrees.set(n.id, 0);
    }

    const validEdges: GraphEdge[] = [];
    const seenEdgeKeys = new Set<string>();

    for (const e of data.edges) {
      if (!nodeMap.has(e.source) || !nodeMap.has(e.target)) continue;
      const key = `${e.source}->${e.target}:${e.id || e.label}`;
      if (seenEdgeKeys.has(key)) continue;
      seenEdgeKeys.add(key);

      validEdges.push(e);
      fwdAdj.get(e.source)?.add(e.target);
      revAdj.get(e.target)?.add(e.source);
      outDegrees.set(e.source, (outDegrees.get(e.source) || 0) + 1);
      inDegrees.set(e.target, (inDegrees.get(e.target) || 0) + 1);
    }

    // Determine Lane Assignments via bounded BFS from target
    const lanes = new Map<string, number>();
    const roles = new Map<string, LayoutNode["role"]>();

    if (tid && nodeMap.has(tid)) {
      lanes.set(tid, 0);
      roles.set(tid, "target");

      // BFS Right (Dependencies: target -> outgoing)
      let currentHop = 1;
      let currentQueue = [tid];
      while (currentQueue.length > 0 && currentHop <= hopDepth) {
        const nextQueue: string[] = [];
        for (const u of currentQueue) {
          for (const v of fwdAdj.get(u) || []) {
            if (!lanes.has(v)) {
              lanes.set(v, currentHop);
              roles.set(v, "dependency");
              nextQueue.push(v);
            }
          }
        }
        currentQueue = nextQueue;
        currentHop++;
      }

      // BFS Left (Dependents: incoming -> target)
      currentHop = 1;
      currentQueue = [tid];
      while (currentQueue.length > 0 && currentHop <= hopDepth) {
        const nextQueue: string[] = [];
        for (const u of currentQueue) {
          for (const v of revAdj.get(u) || []) {
            if (!lanes.has(v)) {
              lanes.set(v, -currentHop);
              roles.set(v, "dependent");
              nextQueue.push(v);
            }
          }
        }
        currentQueue = nextQueue;
        currentHop++;
      }
    }

    // If no target or unreached nodes remain:
    for (const n of allUniqueNodes) {
      if (!lanes.has(n.id)) {
        if (!tid) {
          // Flow topologically by degrees: sources left, intermediate center, sinks right
          const inD = inDegrees.get(n.id) || 0;
          const outD = outDegrees.get(n.id) || 0;
          if (inD === 0 && outD > 0) lanes.set(n.id, -1);
          else if (outD === 0 && inD > 0) lanes.set(n.id, 1);
          else lanes.set(n.id, 0);
          roles.set(n.id, "dependency");
        } else {
          // Unreached nodes in bounded neighborhood
          lanes.set(n.id, 0);
          roles.set(n.id, "isolated");
        }
      }
    }

    // Mark path nodes
    const pathSet = new Set(highlightPathNodes);
    for (const pid of pathSet) {
      if (roles.has(pid) && roles.get(pid) !== "target") {
        roles.set(pid, "path");
      }
    }

    // Filter nodes by type & search query if active
    let visibleNodesList = allUniqueNodes;
    if (selectedTypeFilter !== "ALL") {
      visibleNodesList = visibleNodesList.filter(
        (n) => (n.type || "Module").toUpperCase() === selectedTypeFilter.toUpperCase()
      );
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      visibleNodesList = visibleNodesList.filter(
        (n) =>
          n.id.toLowerCase().includes(q) ||
          (n.label && n.label.toLowerCase().includes(q))
      );
    }

    // Always ensure target is visible if present
    if (tid && nodeMap.has(tid) && !visibleNodesList.some((n) => n.id === tid)) {
      visibleNodesList.push(nodeMap.get(tid)!);
    }

    // Bucket into lanes
    const byLane = new Map<number, GraphNode[]>();
    for (const n of visibleNodesList) {
      const l = lanes.get(n.id) ?? 0;
      if (!byLane.has(l)) byLane.set(l, []);
      byLane.get(l)!.push(n);
    }

    // Sort lanes stably: target first, then by alphabetical ID
    for (const [, list] of byLane.entries()) {
      list.sort((a, b) => {
        if (a.id === tid) return -1;
        if (b.id === tid) return 1;
        return a.id.localeCompare(b.id);
      });
    }

    const sortedLanes = Array.from(byLane.keys()).sort((a, b) => a - b);
    const minLane = sortedLanes[0] ?? 0;
    const maxLane = sortedLanes[sortedLanes.length - 1] ?? 0;
    const laneSpan = Math.max(1, maxLane - minLane + 1);

    const canvasWidth = Math.max(900, laneSpan * LANE_WIDTH + 160);
    const maxNodesInAnyLane = Math.max(
      ...Array.from(byLane.values()).map((l) => l.length),
      1
    );

    // Dynamic vertical spacing to prevent giant canvases
    const vSpacing = Math.min(
      74,
      Math.max(46, Math.floor(480 / Math.min(maxNodesInAnyLane, MAX_NODES_PER_LANE)))
    );
    const canvasHeight = Math.max(
      520,
      Math.min(maxNodesInAnyLane, MAX_NODES_PER_LANE) * vSpacing + 160
    );

    const centerX = canvasWidth / 2;
    const centerY = canvasHeight / 2;

    const positions = new Map<string, { x: number; y: number }>();

    for (const laneNum of sortedLanes) {
      const laneNodes = byLane.get(laneNum) || [];
      const laneX = centerX + laneNum * LANE_WIDTH;

      // If lane has more than MAX_NODES_PER_LANE, stagger into 2 sub-columns
      const isStaggered = laneNodes.length > MAX_NODES_PER_LANE;
      const count = laneNodes.length;

      laneNodes.forEach((node, idx) => {
        let x = laneX;
        let y = centerY;

        if (isStaggered) {
          const colOffset = idx % 2 === 0 ? -45 : 45;
          const rowIdx = Math.floor(idx / 2);
          const totalRows = Math.ceil(count / 2);
          const totalH = (totalRows - 1) * vSpacing;
          x = laneX + colOffset;
          y = centerY - totalH / 2 + rowIdx * vSpacing;
        } else {
          const totalH = (count - 1) * vSpacing;
          y = centerY - totalH / 2 + idx * vSpacing;
        }

        positions.set(node.id, { x, y });
      });
    }

    const visibleNodeIds = new Set(visibleNodesList.map((n) => n.id));
    const layoutEdges = validEdges.filter(
      (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
    );

    const layoutNodes: LayoutNode[] = visibleNodesList.map((n) => {
      const pos = positions.get(n.id) || { x: centerX, y: centerY };
      return {
        ...n,
        x: pos.x,
        y: pos.y,
        lane: lanes.get(n.id) ?? 0,
        role: roles.get(n.id) ?? "dependency",
        inDegree: inDegrees.get(n.id) ?? 0,
        outDegree: outDegrees.get(n.id) ?? 0,
      };
    });

    return {
      nodes: layoutNodes,
      edges: layoutEdges,
      width: canvasWidth,
      height: canvasHeight,
      totalAvailableNodes,
      totalAvailableEdges,
    };
  }, [
    data,
    targetNodeId,
    hopDepth,
    selectedTypeFilter,
    searchQuery,
    highlightPathNodes,
  ]);

  // Viewport interactions: mouse dragging
  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    // Only pan if clicking canvas background (not on node/edge directly)
    if ((e.target as HTMLElement).tagName === "svg" || (e.target as HTMLElement).tagName === "rect") {
      setIsPanning(true);
      setStartPan({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (isPanning) {
      setPan({
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y,
      });
    }
  };

  const handleMouseUp = () => setIsPanning(false);

  // Smooth non-passive wheel zoom
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;
    const handleNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      setZoom((prev) => Math.min(2.5, Math.max(0.35, prev * factor)));
    };
    svgEl.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      svgEl.removeEventListener("wheel", handleNativeWheel);
    };
  }, [data]);

  const handleZoomIn = () => setZoom((z) => Math.min(2.5, z * 1.2));
  const handleZoomOut = () => setZoom((z) => Math.max(0.35, z / 1.2));
  const handleResetView = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const handleFitToView = useCallback(() => {
    setZoom(0.85);
    setPan({ x: 0, y: 0 });
  }, []);

  if (isLoading) {
    return (
      <div
        style={{
          height: "480px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <div style={{ textAlign: "center", color: "var(--text-secondary)" }}>
          <Layers
            size={36}
            style={{
              animation: "spin 2s linear infinite",
              color: "var(--accent-blue)",
              marginBottom: "0.75rem",
            }}
          />
          <h4 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Querying Connected Graph Data...</h4>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
            Extracting modules, directed edges, and relationship paths from FalkorDB.
          </p>
        </div>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div
        style={{
          height: "480px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          padding: "2rem",
          textAlign: "center",
        }}
      >
        <Layers size={42} color="var(--border-strong)" style={{ marginBottom: "0.75rem" }} />
        <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          No graph nodes selected
        </h3>
        <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", maxWidth: "420px", marginTop: "0.3rem" }}>
          Select a module or run an investigation to render the live dependency graph.
        </p>
      </div>
    );
  }

  const { nodes, edges, width, height, totalAvailableNodes, totalAvailableEdges } = layout;
  const pathSet = new Set(highlightPathNodes);

  return (
    <div
      ref={containerRef}
      style={{
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--bg-card)",
        borderRadius: "8px",
        border: "1px solid var(--border-subtle)",
        boxShadow: "var(--shadow-sm)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* ── Top Toolbar: Scope, Search, Filters, and Controls ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          padding: "0.6rem 1rem",
          backgroundColor: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border-subtle)",
          gap: "0.75rem",
          fontSize: "0.8rem",
        }}
      >
        {/* Left: Search & Hop Depth */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
          {/* Search Input */}
          <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
            <Search size={13} style={{ position: "absolute", left: "0.55rem", color: "var(--text-muted)" }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search module in view..."
              style={{
                padding: "0.3rem 0.55rem 0.3rem 1.7rem",
                borderRadius: "5px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.76rem",
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-primary)",
                width: "180px",
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: "0.4rem",
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Mode Toggle: Investigation Path vs Network Overview */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "5px",
              overflow: "hidden",
            }}
          >
            <button
              onClick={() => setGraphViewMode("path")}
              title="Investigation Path view focused on active target and path"
              style={{
                border: "none",
                padding: "0.22rem 0.55rem",
                fontSize: "0.72rem",
                fontWeight: 600,
                backgroundColor: graphViewMode === "path" ? "var(--accent-blue)" : "transparent",
                color: graphViewMode === "path" ? "#ffffff" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              Path View
            </button>
            <button
              onClick={() => setGraphViewMode("overview")}
              title="Network Overview of module dependency topology"
              style={{
                border: "none",
                borderLeft: "1px solid var(--border-subtle)",
                padding: "0.22rem 0.55rem",
                fontSize: "0.72rem",
                fontWeight: 600,
                backgroundColor: graphViewMode === "overview" ? "var(--accent-blue)" : "transparent",
                color: graphViewMode === "overview" ? "#ffffff" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              Overview
            </button>
          </div>

          {/* Hop Depth Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--text-secondary)" }}>
            <span style={{ fontSize: "0.72rem", fontWeight: 600 }}>Hop Range:</span>
            {[1, 2, 3].map((d) => (
              <button
                key={d}
                onClick={() => setHopDepth(d as 1 | 2 | 3)}
                style={{
                  padding: "0.2rem 0.5rem",
                  borderRadius: "4px",
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  border: "1px solid",
                  borderColor: hopDepth === d ? "var(--accent-blue)" : "var(--border-subtle)",
                  backgroundColor: hopDepth === d ? "var(--accent-blue)" : "var(--bg-primary)",
                  color: hopDepth === d ? "#ffffff" : "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                {d === 3 ? "All" : `${d}-Hop`}
              </button>
            ))}
          </div>


          {/* Node Type Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <Filter size={12} color="var(--text-muted)" />
            <select
              value={selectedTypeFilter}
              onChange={(e) => setSelectedTypeFilter(e.target.value)}
              style={{
                padding: "0.25rem 0.45rem",
                borderRadius: "4px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.72rem",
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-primary)",
              }}
            >
              <option value="ALL">All Types</option>
              <option value="Module">Modules</option>
              <option value="File">Files</option>
            </select>
          </div>
        </div>

        {/* Right: Metrics & Viewport Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {/* Rendered vs Available Counts */}
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 500 }}>
            Showing <strong>{nodes.length}</strong> of {totalAvailableNodes} nodes •{" "}
            <strong>{edges.length}</strong> of {totalAvailableEdges} edges
          </span>

          {/* Viewport Zoom & Fit Buttons */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "5px",
              overflow: "hidden",
            }}
          >
            <button
              onClick={handleZoomIn}
              title="Zoom In"
              style={{
                border: "none",
                background: "transparent",
                padding: "0.3rem 0.5rem",
                cursor: "pointer",
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
              }}
            >
              <ZoomIn size={14} />
            </button>
            <button
              onClick={handleZoomOut}
              title="Zoom Out"
              style={{
                border: "none",
                borderLeft: "1px solid var(--border-subtle)",
                background: "transparent",
                padding: "0.3rem 0.5rem",
                cursor: "pointer",
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
              }}
            >
              <ZoomOut size={14} />
            </button>
            <button
              onClick={handleFitToView}
              title="Fit to View"
              style={{
                border: "none",
                borderLeft: "1px solid var(--border-subtle)",
                background: "transparent",
                padding: "0.3rem 0.5rem",
                cursor: "pointer",
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
              }}
            >
              <Maximize2 size={13} />
            </button>
            <button
              onClick={handleResetView}
              title="Reset View"
              style={{
                border: "none",
                borderLeft: "1px solid var(--border-subtle)",
                background: "transparent",
                padding: "0.3rem 0.5rem",
                cursor: "pointer",
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
              }}
            >
              <RotateCcw size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Multi-Hop Verified Path Banner (if active) ── */}
      {highlightPathNodes.length >= 2 && (
        <div
          style={{
            backgroundColor: "var(--accent-blue-subtle)",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "0.45rem 1rem",
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            fontSize: "0.75rem",
            flexWrap: "wrap",
          }}
        >
          <Compass size={14} color="var(--accent-blue)" />
          {(() => {
            const hopCount = highlightPathNodes.length - 1;
            const hopLabel =
              hopCount <= 0
                ? "No path established"
                : hopCount === 1
                ? "Direct Relationship (1-hop path)"
                : `Verified Multi-Hop Path (${hopCount} hops)`;
            return <strong style={{ color: "var(--accent-blue)" }}>{hopLabel}:</strong>;
          })()}
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap" }}>
            {highlightPathNodes.map((pNode, idx) => (
              <React.Fragment key={pNode}>
                <button
                  onClick={() => {
                    const match = nodes.find((n) => n.id === pNode);
                    if (match) setSelectedNode(match);
                  }}
                  style={{
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--accent-blue)",
                    borderRadius: "4px",
                    padding: "0.15rem 0.45rem",
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {pNode.replace(/^mod:/, "")}
                </button>
                {idx < highlightPathNodes.length - 1 && (
                  <ArrowRight size={12} color="var(--accent-blue)" />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* ── Main Canvas Viewport ── */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "530px",
          overflow: "hidden",
          cursor: isPanning ? "grabbing" : "grab",
          backgroundColor: "var(--bg-primary)",
        }}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          style={{
            width: "100%",
            height: "100%",
            display: "block",
            userSelect: "none",
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            {/* Arrowhead Markers */}
            <marker
              id="arrow-default"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="var(--border-strong)" />
            </marker>
            <marker
              id="arrow-hover"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--accent-blue)" />
            </marker>
            <marker
              id="arrow-path"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b" />
            </marker>
            <marker
              id="arrow-broken"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#ef4444" />
            </marker>
            <marker
              id="arrow-surviving"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#10b981" />
            </marker>
          </defs>

          {/* Canvas Background Rect for dragging */}
          <rect width={width} height={height} fill="transparent" />

          {/* Group containing transformed graph contents */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {/* Lane Divider Guides */}
            {Array.from(new Set(nodes.map((n) => Math.round(n.x)))).map((laneX) => (
              <line
                key={`guide-${laneX}`}
                x1={laneX}
                y1={30}
                x2={laneX}
                y2={height - 30}
                stroke="var(--border-subtle)"
                strokeDasharray="4,4"
                strokeWidth={1}
                opacity={0.7}
              />
            ))}

            {/* Lane Header Labels */}
            {[-2, -1, 0, 1, 2].map((l) => {
              const xPos = width / 2 + l * LANE_WIDTH;
              let labelText = "";
              if (l === 0) labelText = "Target Focus (Center)";
              else if (l < 0) labelText = `Upstream Callers (${Math.abs(l)}-Hop Left)`;
              else labelText = `Dependencies (${l}-Hop Right)`;

              return (
                <text
                  key={`lane-lbl-${l}`}
                  x={xPos}
                  y={24}
                  textAnchor="middle"
                  fontSize="10px"
                  fontWeight={700}
                  fill="var(--text-muted)"
                  letterSpacing="0.04em"
                >
                  {labelText}
                </text>
              );
            })}

            {/* ── Directed Edges ── */}
            {edges.map((edge) => {
              const src = nodes.find((n) => n.id === edge.source);
              const dst = nodes.find((n) => n.id === edge.target);
              if (!src || !dst) return null;

              const isDisrupted =
                disappearedEdgeIds.includes(edge.id) ||
                disappearedNodeIds.includes(edge.source) ||
                disappearedNodeIds.includes(edge.target);
              const isSurviving =
                survivingNodeIds.includes(edge.source) || survivingNodeIds.includes(edge.target);
              const isPathEdge =
                pathSet.has(edge.source) && pathSet.has(edge.target);
              const isHovered =
                hoveredEdgeId === edge.id ||
                hoveredNodeId === edge.source ||
                hoveredNodeId === edge.target;
              const isSelected =
                selectedEdge?.id === edge.id ||
                (selectedNode?.id === edge.source || selectedNode?.id === edge.target);

              let stroke = "var(--border-strong)";
              let strokeWidth = 1.6;
              let dashed: string | undefined;
              let marker = "url(#arrow-default)";
              let opacity = 0.7;

              if (isDisrupted) {
                stroke = "#ef4444";
                strokeWidth = 2.4;
                dashed = "5,4";
                marker = "url(#arrow-broken)";
                opacity = 1;
              } else if (isPathEdge) {
                stroke = "#f59e0b";
                strokeWidth = 3;
                marker = "url(#arrow-path)";
                opacity = 1;
              } else if (isSelected || isHovered) {
                stroke = "var(--accent-blue)";
                strokeWidth = 2.8;
                marker = "url(#arrow-hover)";
                opacity = 1;
              } else if (isSurviving) {
                stroke = "#10b981";
                strokeWidth = 2.2;
                marker = "url(#arrow-surviving)";
                opacity = 0.95;
              }

              // Offset endpoints to sit on node border
              const srcRadius = src.id === targetNodeId ? NODE_RADIUS_TARGET : NODE_RADIUS_DEFAULT;
              const dstRadius = dst.id === targetNodeId ? NODE_RADIUS_TARGET : NODE_RADIUS_DEFAULT;
              const dx = dst.x - src.x;
              const dy = dst.y - src.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;

              const x1 = src.x + (dx / dist) * (srcRadius + 2);
              const y1 = src.y + (dy / dist) * (srcRadius + 2);
              const x2 = dst.x - (dx / dist) * (dstRadius + 4);
              const y2 = dst.y - (dy / dist) * (dstRadius + 4);

              return (
                <g key={`edge-${edge.source}->${edge.target}-${edge.id}`}>
                  {/* Invisible thicker stroke for easier clicking */}
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="transparent"
                    strokeWidth={14}
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      setSelectedEdge(edge);
                      setSelectedNode(null);
                    }}
                    onMouseEnter={() => setHoveredEdgeId(edge.id)}
                    onMouseLeave={() => setHoveredEdgeId(null)}
                  />
                  {/* Visible edge line */}
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={stroke}
                    strokeWidth={strokeWidth}
                    strokeDasharray={dashed}
                    markerEnd={marker}
                    opacity={opacity}
                    style={{ pointerEvents: "none", transition: "stroke 0.15s ease" }}
                  />
                </g>
              );
            })}

            {/* ── Nodes ── */}
            {nodes.map((node) => {
              const isTarget = node.id === targetNodeId || node.role === "target";
              const isDisrupted = disappearedNodeIds.includes(node.id);
              const isSurviving = !isTarget && survivingNodeIds.includes(node.id);
              const isPath = pathSet.has(node.id);
              const isSelected = selectedNode?.id === node.id;
              const isHovered = hoveredNodeId === node.id;

              const radius = isTarget ? NODE_RADIUS_TARGET : NODE_RADIUS_DEFAULT;

              let fill = "var(--bg-card)";
              let stroke = "var(--border-strong)";
              let strokeWidth = 1.8;

              if (isTarget) {
                fill = "var(--accent-blue)";
                stroke = "var(--accent-blue-hover)";
                strokeWidth = 3;
              } else if (isDisrupted) {
                fill = "var(--status-contradicted-bg)";
                stroke = "#ef4444";
                strokeWidth = 2.4;
              } else if (isPath) {
                fill = "#fef3c7";
                stroke = "#f59e0b";
                strokeWidth = 2.6;
              } else if (isSurviving) {
                fill = "var(--status-verified-bg)";
                stroke = "#10b981";
                strokeWidth = 2.2;
              } else if (isSelected || isHovered) {
                stroke = "var(--accent-blue)";
                strokeWidth = 2.6;
              } else if (node.role === "dependent") {
                stroke = "#6366f1"; // Indigo for callers
                strokeWidth = 2;
              } else if (node.role === "dependency") {
                stroke = "#0284c7"; // Sky for callees
                strokeWidth = 2;
              }

              const cleanLabel = (node.label || node.id).replace(/^mod:/, "");
              const maxChars = isTarget ? 18 : 14;
              const displayLabel =
                cleanLabel.length > maxChars
                  ? `${cleanLabel.slice(0, maxChars - 1)}…`
                  : cleanLabel;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={() => {
                    setSelectedNode(selectedNode?.id === node.id ? null : node);
                    setSelectedEdge(null);
                  }}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Target pulse/glow ring */}
                  {isTarget && (
                    <circle
                      r={radius + 8}
                      fill="none"
                      stroke="var(--accent-blue)"
                      strokeWidth={1.5}
                      strokeDasharray="4,3"
                      opacity={0.6}
                    />
                  )}

                  {/* Path highlight ring */}
                  {isPath && !isTarget && (
                    <circle
                      r={radius + 5}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="3,2"
                    />
                  )}

                  {/* Selection indicator ring */}
                  {isSelected && (
                    <circle
                      r={radius + 6}
                      fill="none"
                      stroke="var(--accent-blue)"
                      strokeWidth={2}
                    />
                  )}

                  {/* Core Node Circle */}
                  <circle
                    r={radius}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={strokeWidth}
                    style={{ transition: "all 0.15s ease" }}
                  />

                  {/* Target Icon or Initial */}
                  {isTarget ? (
                    <text
                      textAnchor="middle"
                      dy="4px"
                      fontSize="11px"
                      fontWeight={700}
                      fill="#ffffff"
                    >
                      ★
                    </text>
                  ) : (
                    <text
                      textAnchor="middle"
                      dy="3.5px"
                      fontSize="9px"
                      fontWeight={600}
                      fill={isPath ? "#92400e" : "var(--text-secondary)"}
                    >
                      {node.role === "dependent" ? "▲" : node.role === "dependency" ? "▼" : "●"}
                    </text>
                  )}

                  {/* Label below node */}
                  <text
                    dy={radius + 14}
                    textAnchor="middle"
                    fontSize={isTarget ? "11px" : "10px"}
                    fontWeight={isTarget ? 700 : 500}
                    fill={
                      isTarget
                        ? "var(--accent-blue)"
                        : isDisrupted
                        ? "#b91c1c"
                        : isPath
                        ? "#b45309"
                        : "var(--text-primary)"
                    }
                  >
                    {displayLabel}
                  </text>

                  {/* Role sub-badge */}
                  {!isTarget && (
                    <text
                      dy={radius + 25}
                      textAnchor="middle"
                      fontSize="8px"
                      fontWeight={600}
                      fill={
                        node.role === "dependent"
                          ? "#6366f1"
                          : node.role === "dependency"
                          ? "#0284c7"
                          : "var(--text-muted)"
                      }
                    >
                      {node.role === "dependent"
                        ? "▲ Caller"
                        : node.role === "dependency"
                        ? "▼ Dep"
                        : isPath
                        ? "★ Path"
                        : ""}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* ── Contextual Inspector Drawer (Right Overlay) ── */}
        {(selectedNode || selectedEdge) && (
          <div
            style={{
              position: "absolute",
              top: "12px",
              right: "12px",
              width: "310px",
              maxHeight: "90%",
              backgroundColor: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "8px",
              boxShadow: "var(--shadow-md)",
              padding: "1rem",
              overflowY: "auto",
              fontSize: "0.8rem",
              zIndex: 10,
            }}
          >
            {/* Header with Close Button */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--border-subtle)",
                paddingBottom: "0.5rem",
                marginBottom: "0.75rem",
              }}
            >
              <span style={{ fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                <Info size={14} color="var(--accent-blue)" />
                {selectedNode ? "Module Inspector" : "Relationship Evidence"}
              </span>
              <button
                onClick={() => {
                  setSelectedNode(null);
                  setSelectedEdge(null);
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-muted)",
                }}
              >
                <X size={15} />
              </button>
            </div>

            {/* Selected Node Details */}
            {selectedNode && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>NAME</div>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)", wordBreak: "break-all" }}>
                    {selectedNode.label || selectedNode.id}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>IDENTIFIER</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--text-secondary)", wordBreak: "break-all" }}>
                    {selectedNode.id}
                  </div>
                </div>

                <div style={{ display: "flex", gap: "1rem" }}>
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>ROLE</div>
                    <span
                      style={{
                        padding: "0.15rem 0.45rem",
                        borderRadius: "4px",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        backgroundColor:
                          selectedNode.role === "target"
                            ? "var(--accent-blue-subtle)"
                            : selectedNode.role === "dependent"
                            ? "#e0e7ff"
                            : "#e0f2fe",
                        color:
                          selectedNode.role === "target"
                            ? "var(--accent-blue)"
                            : selectedNode.role === "dependent"
                            ? "#4338ca"
                            : "#0369a1",
                      }}
                    >
                      {selectedNode.role.toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>TYPE</div>
                    <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                      {selectedNode.type || "Module"}
                    </span>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginTop: "0.2rem" }}>
                  <div style={{ padding: "0.4rem", borderRadius: "5px", backgroundColor: "var(--bg-primary)" }}>
                    <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>IN-DEGREE (CALLERS)</div>
                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      {selectedNode.inDegree}
                    </div>
                  </div>
                  <div style={{ padding: "0.4rem", borderRadius: "5px", backgroundColor: "var(--bg-primary)" }}>
                    <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>OUT-DEGREE (DEPS)</div>
                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      {selectedNode.outDegree}
                    </div>
                  </div>
                </div>

                {onSelectTarget && selectedNode.id !== targetNodeId && (
                  <button
                    onClick={() => {
                      onSelectTarget(selectedNode.id);
                      setSelectedNode(null);
                    }}
                    style={{
                      marginTop: "0.5rem",
                      padding: "0.45rem 0.75rem",
                      borderRadius: "6px",
                      border: "none",
                      backgroundColor: "var(--accent-blue)",
                      color: "#ffffff",
                      fontWeight: 600,
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <Compass size={13} />
                    Focus as Investigation Target
                  </button>
                )}

                {onOpenSourceFile && (
                  <button
                    onClick={() => {
                      const cleanMod = selectedNode.id.replace(/^mod:/, "");
                      const fileGuess = cleanMod.replace(/\./g, "/") + ".py";
                      onOpenSourceFile(fileGuess);
                    }}
                    style={{
                      marginTop: "0.4rem",
                      padding: "0.45rem 0.75rem",
                      borderRadius: "6px",
                      border: "1px solid var(--border-subtle)",
                      backgroundColor: "var(--bg-card)",
                      color: "var(--text-primary)",
                      fontWeight: 600,
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <FileCode size={13} color="var(--accent-blue)" />
                    Inspect Source in Explorer
                  </button>
                )}
              </div>
            )}


            {/* Selected Edge Details */}
            {selectedEdge && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>RELATIONSHIP</div>
                  <div style={{ fontWeight: 700, color: "var(--accent-blue)" }}>
                    {selectedEdge.label || "DEPENDS_ON"}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>CALLER (SOURCE)</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", wordBreak: "break-all" }}>
                    {selectedEdge.source}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>CALLEE (TARGET)</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", wordBreak: "break-all" }}>
                    {selectedEdge.target}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>EVIDENCE TYPE</div>
                  <span
                    style={{
                      padding: "0.15rem 0.45rem",
                      borderRadius: "4px",
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      backgroundColor: "var(--status-verified-bg)",
                      color: "var(--status-verified-text)",
                    }}
                  >
                    {selectedEdge.evidence_type || "observed (AST import)"}
                  </span>
                </div>

                {Boolean(selectedEdge.properties?.source_file) && (
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>SOURCE FILE</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--text-secondary)", wordBreak: "break-all" }}>
                      {String(selectedEdge.properties?.source_file || "")}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Visual Legend Footer ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          padding: "0.45rem 1rem",
          backgroundColor: "var(--bg-secondary)",
          borderTop: "1px solid var(--border-subtle)",
          fontSize: "0.72rem",
          color: "var(--text-muted)",
          gap: "0.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: "var(--accent-blue)" }} />
            Target Focus
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid #6366f1", backgroundColor: "transparent" }} />
            Upstream Caller (Left)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid #0284c7", backgroundColor: "transparent" }} />
            Dependency (Right)
          </span>
          {highlightPathNodes.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: "#fef3c7", border: "2px solid #f59e0b" }} />
              Active Path Hop
            </span>
          )}
          {disappearedEdgeIds.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <span style={{ width: 12, height: 2, borderBottom: "2px dashed #ef4444" }} />
              Disrupted Scenario Edge
            </span>
          )}
        </div>
        <span>→ Directed arrows point in canonical DEPENDS_ON direction</span>
      </div>
    </div>
  );
};
