import React from "react";
import { CheckCircle2, CircleDashed, Lightbulb } from "lucide-react";

export const RoadmapCard: React.FC = () => {
  return (
    <div
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "0.75rem",
        padding: "1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <Lightbulb size={20} color="var(--accent-cyan)" />
        <h2 style={{ fontSize: "1.1rem", fontWeight: 600 }}>Architecture & Implementation Status</h2>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "1.5rem",
        }}
      >
        {/* Phase 1 Validated */}
        <div
          style={{
            backgroundColor: "rgba(16, 185, 129, 0.04)",
            border: "1px solid rgba(16, 185, 129, 0.2)",
            borderRadius: "0.5rem",
            padding: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "#34d399",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              Phase 1 Completed & Verified
            </span>
          </div>
          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>FalkorDB v4.4.1 running with persistent volume</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>FastAPI liveness & honest readiness endpoints</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>GRAPH.COPY & isolated scenario graph branching verified</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>Native PageRank & ShortestPath procedures tested</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>Restricted MCP diagnostic server with typed contracts</span>
            </li>
          </ul>
        </div>

        {/* Phase 2 Planned Intelligence */}
        <div
          style={{
            backgroundColor: "rgba(59, 130, 246, 0.04)",
            border: "1px solid rgba(59, 130, 246, 0.2)",
            borderRadius: "0.5rem",
            padding: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "#60a5fa",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              Phase 2 Intelligence Roadmap
            </span>
          </div>
          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CircleDashed size={16} color="#60a5fa" />
              <span>Git repository parsing & full graph model ingestion</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CircleDashed size={16} color="#60a5fa" />
              <span>4-hop reverse-dependency impact traversal (trace_impact)</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CircleDashed size={16} color="#60a5fa" />
              <span>Reviewer discovery & ownership ranking (who_knows)</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CircleDashed size={16} color="#60a5fa" />
              <span>Full counterfactual graph deletion & before/after diffing</span>
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
              <CircleDashed size={16} color="#60a5fa" />
              <span>Interactive visual graph explorer & GitHub issue creator</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
