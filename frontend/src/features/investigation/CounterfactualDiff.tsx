import React from "react";
import type { SimulationResult } from "../../types/investigation";
import { GitFork, AlertTriangle } from "lucide-react";


interface CounterfactualDiffProps {
  simulation: SimulationResult | null;
  activeView: "baseline" | "scenario";
  onToggleView: (view: "baseline" | "scenario") => void;
}

export const CounterfactualDiff: React.FC<CounterfactualDiffProps> = ({
  simulation,
  activeView,
  onToggleView,
}) => {
  if (!simulation) {
    return (
      <div
        style={{
          padding: "1.5rem",
          textAlign: "center",
          color: "var(--text-muted)",
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          fontSize: "0.85rem",
        }}
      >
        <GitFork size={28} color="var(--border-strong)" style={{ marginBottom: "0.5rem" }} />
        <p>No counterfactual simulation executed yet.</p>
        <p style={{ fontSize: "0.78rem", marginTop: "0.25rem" }}>
          Run simulate_remove_module to clone the graph and inspect isolated blast radius.
        </p>
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
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem",
          backgroundColor: "var(--bg-muted)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <GitFork size={16} color="var(--accent-blue)" />
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Counterfactual Simulation (Isolated Graph Copy)
          </h3>
        </div>

        {/* View Toggle */}
        <div
          style={{
            display: "flex",
            backgroundColor: "#ffffff",
            padding: "0.15rem",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <button
            onClick={() => onToggleView("baseline")}
            style={{
              padding: "0.25rem 0.65rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "4px",
              border: "none",
              backgroundColor: activeView === "baseline" ? "var(--accent-blue)" : "transparent",
              color: activeView === "baseline" ? "#ffffff" : "var(--text-secondary)",
              transition: "all 0.15s ease",
            }}
          >
            Baseline Graph
          </button>
          <button
            onClick={() => onToggleView("scenario")}
            style={{
              padding: "0.25rem 0.65rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "4px",
              border: "none",
              backgroundColor: activeView === "scenario" ? "#e11d48" : "transparent",
              color: activeView === "scenario" ? "#ffffff" : "var(--text-secondary)",
              transition: "all 0.15s ease",
            }}
          >
            Scenario (Removed)
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "0.5rem",
          padding: "0.75rem 1rem",
          backgroundColor: "#fafafa",
          borderBottom: "1px solid var(--border-subtle)",
          fontSize: "0.78rem",
        }}
      >
        <div>
          <span style={{ color: "var(--text-muted)", display: "block" }}>Disrupted Paths</span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#e11d48" }}>
            {simulation.disappeared_paths_count}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--text-muted)", display: "block" }}>Blast Radius</span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent-blue)" }}>
            {(simulation.blast_radius_score * 100).toFixed(1)}%
          </span>
        </div>
        <div>
          <span style={{ color: "var(--text-muted)", display: "block" }}>Surviving Modules</span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
            {simulation.surviving_modules_count}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--text-muted)", display: "block" }}>Surviving Edges</span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
            {simulation.surviving_edges_count}
          </span>
        </div>
      </div>

      {/* Disrupted Paths List */}
      <div style={{ padding: "0.75rem 1rem" }}>
        <h4 style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.4rem", color: "var(--text-primary)" }}>
          Disrupted Dependency Paths ({simulation.disappeared_paths.length})
        </h4>

        {simulation.disappeared_paths.length === 0 ? (
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
            No upstream dependent modules rely on this target.
          </p>
        ) : (
          <div
            style={{
              maxHeight: "150px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            {simulation.disappeared_paths.map((p, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: "0.74rem",
                  fontFamily: "var(--font-mono)",
                  padding: "0.35rem 0.5rem",
                  backgroundColor: "var(--status-contradicted-bg)",
                  border: "1px solid var(--status-contradicted-border)",
                  borderRadius: "4px",
                  color: "#be123c",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <span style={{ fontWeight: 700 }}>✕</span>
                <span>{p.broken_path.join(" ➔ ")}</span>
              </div>
            ))}
          </div>
        )}

        {/* Disclaimer */}
        <div
          style={{
            marginTop: "0.75rem",
            padding: "0.5rem 0.75rem",
            backgroundColor: "var(--status-unknown-bg)",
            border: "1px solid var(--status-unknown-border)",
            borderRadius: "4px",
            fontSize: "0.72rem",
            color: "var(--status-unknown-text)",
            display: "flex",
            alignItems: "flex-start",
            gap: "0.4rem",
          }}
        >
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: "0.1rem" }} />
          <span>{simulation.disclaimer}</span>
        </div>
      </div>
    </div>
  );
};
