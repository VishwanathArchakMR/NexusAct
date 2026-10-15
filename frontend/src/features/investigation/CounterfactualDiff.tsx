import React, { useState } from "react";
import type { SimulationResult } from "../../types/investigation";
import { GitFork, AlertTriangle, CheckCircle2, Info } from "lucide-react";

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
  const [showSurviving, setShowSurviving] = useState(false);

  if (!simulation) {
    return (
      <div style={emptyStyle}>
        <GitFork size={28} color="var(--border-strong)" style={{ marginBottom: "0.5rem" }} />
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          No counterfactual simulation executed yet.
        </p>
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
          Run <code>simulate_remove_module</code> to clone the graph and compare before/after paths.
        </p>
      </div>
    );
  }

  const blastPct = ((simulation.blast_radius_score ?? 0) * 100).toFixed(1);
  const disappearedPaths = simulation.disappeared_paths ?? [];
  const survivingPaths = simulation.surviving_paths ?? [];
  const isolatedModules = simulation.newly_isolated_modules ?? [];
  const hasDisrupted = disappearedPaths.length > 0;
  const hasSurviving = survivingPaths.length > 0;

  return (
    <div style={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid var(--border-subtle)", overflow: "hidden" }}>
      {/* ── Header ── */}
      <div style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <GitFork size={16} color="var(--accent-blue)" />
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Counterfactual Simulation — Removed:{" "}
            <code style={{ fontFamily: "var(--font-mono)", color: "#e11d48" }}>
              {simulation.target_module_name}
            </code>
          </h3>
          {simulation.is_incomplete && (
            <span style={incompleteBadge}>⚠ Partial results (path limit reached)</span>
          )}
        </div>

        {/* View Toggle */}
        <div style={toggleContainerStyle}>
          <button
            onClick={() => onToggleView("baseline")}
            style={toggleBtnStyle(activeView === "baseline", "blue")}
          >
            Baseline
          </button>
          <button
            onClick={() => onToggleView("scenario")}
            style={toggleBtnStyle(activeView === "scenario", "red")}
          >
            Scenario (removed)
          </button>
        </div>
      </div>

      {/* ── Metrics Row ── */}
      <div style={metricsGridStyle}>
        <MetricCard
          label="Baseline Paths"
          value={simulation.baseline_paths_count}
          color="var(--text-secondary)"
          title="Total upstream dependency paths to target in unmodified graph"
        />
        <MetricCard
          label="Broken Paths"
          value={simulation.disappeared_paths_count}
          color="#e11d48"
          title="Paths from baseline that no longer reach any destination after target removal"
        />
        <MetricCard
          label="Surviving Paths"
          value={simulation.surviving_paths_count}
          color="#16a34a"
          title="Upstream paths that still reach a valid destination via an alternate route"
        />
        <MetricCard
          label={`Blast Radius — ${blastPct}%`}
          value={`${blastPct}%`}
          color={simulation.blast_radius_score > 0.5 ? "#e11d48" : "#d97706"}
          title="broken_paths / baseline_paths_count — fraction of known upstream paths disrupted. Does not imply runtime failure probability."
        />
        <MetricCard
          label="Surviving Modules"
          value={simulation.surviving_modules_count}
          color="var(--text-primary)"
          title="Total modules remaining in the scenario copy graph"
        />
        <MetricCard
          label="Surviving Edges"
          value={simulation.surviving_edges_count}
          color="var(--text-primary)"
          title="Total edges remaining in the scenario copy graph"
        />
      </div>

      {/* ── Before/After Path Comparison ── */}
      <div style={{ padding: "0.85rem 1rem" }}>

        {/* Disrupted (Broken) Paths */}
        <div style={{ marginBottom: "0.85rem" }}>
          <h4 style={sectionHeadingStyle}>
            <span style={{ color: "#e11d48" }}>✕</span>&nbsp;
            Broken Paths ({disappearedPaths.length}
            {(simulation.disappeared_paths_count ?? 0) > disappearedPaths.length
              ? ` of ${simulation.disappeared_paths_count} shown`
              : ""})
            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 400, marginLeft: "0.5rem" }}>
              — paths that routed through the removed module and no longer exist in the scenario graph
            </span>
          </h4>

          {!hasDisrupted ? (
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
              No upstream paths were broken by this removal.
            </p>
          ) : (
            <div style={pathListStyle}>
              {disappearedPaths.map((p, idx) => (
                <div key={idx} style={brokenPathRowStyle}>
                  <span style={{ fontWeight: 700, color: "#be123c", flexShrink: 0 }}>✕</span>
                  <span style={{ color: "#475569", fontSize: "0.72rem", marginRight: "0.5rem" }}>
                    {p.hops} hop{p.hops !== 1 ? "s" : ""}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "#be123c" }}>
                    {p.broken_path.join(" ➔ ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Surviving Paths (alternate routes) */}
        <div style={{ marginBottom: "0.85rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
            <h4 style={sectionHeadingStyle}>
              <CheckCircle2 size={13} color="#16a34a" style={{ verticalAlign: "middle" }} />&nbsp;
              Surviving Paths ({survivingPaths.length}
              {(simulation.surviving_paths_count ?? 0) > survivingPaths.length
                ? ` of ${simulation.surviving_paths_count} shown`
                : ""})
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 400, marginLeft: "0.5rem" }}>
                — alternate upstream routes verified in the scenario copy
              </span>
            </h4>
            {hasSurviving && (
              <button
                onClick={() => setShowSurviving((v) => !v)}
                style={{ fontSize: "0.72rem", border: "none", background: "none", color: "var(--accent-blue)", cursor: "pointer" }}
              >
                {showSurviving ? "Hide" : "Show"}
              </button>
            )}
          </div>

          {!hasSurviving ? (
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
              No alternate upstream paths survive this removal — all routes intersected the removed module.
            </p>
          ) : showSurviving ? (
            <div style={pathListStyle}>
              {survivingPaths.map((p, idx) => (
                <div key={idx} style={survivingPathRowStyle}>
                  <CheckCircle2 size={12} color="#16a34a" style={{ flexShrink: 0 }} />
                  <span style={{ color: "#475569", fontSize: "0.72rem", marginRight: "0.5rem" }}>
                    {p.hops} hop{p.hops !== 1 ? "s" : ""}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "#15803d" }}>
                    {p.surviving_path.join(" ➔ ")}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: "0.78rem", color: "#16a34a" }}>
              {simulation.surviving_paths_count ?? 0} alternate path(s) confirmed in scenario graph.
            </p>
          )}
        </div>

        {/* Newly Isolated */}
        {isolatedModules.length > 0 && (
          <div style={{ marginBottom: "0.85rem" }}>
            <h4 style={sectionHeadingStyle}>
              <Info size={13} color="#d97706" style={{ verticalAlign: "middle" }} />&nbsp;
              Newly Isolated Modules ({isolatedModules.length})
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 400, marginLeft: "0.5rem" }}>
                — modules whose only outgoing dependency was the removed target
              </span>
            </h4>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
              {isolatedModules.map((id) => (
                <code key={id} style={{ fontSize: "0.72rem", padding: "0.2rem 0.4rem", backgroundColor: "#fef3c7", border: "1px solid #fcd34d", borderRadius: "3px", color: "#92400e" }}>
                  {id}
                </code>
              ))}
            </div>
          </div>
        )}

        {/* Disclaimer */}
        <div style={disclaimerStyle}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: "0.1rem" }} />
          <span>
            <strong>Blast radius formula:</strong> broken_paths / baseline_paths_count ({simulation.disappeared_paths_count} / {simulation.baseline_paths_count} = {blastPct}%).&nbsp;
            {simulation.disclaimer}
          </span>
        </div>
      </div>
    </div>
  );
};

// ── Sub-components ──────────────────────────────────────────────────────────

const MetricCard: React.FC<{ label: string; value: string | number; color: string; title?: string }> = ({
  label, value, color, title
}) => (
  <div title={title} style={{ cursor: title ? "help" : undefined }}>
    <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.72rem", marginBottom: "0.15rem" }}>{label}</span>
    <span style={{ fontSize: "1.1rem", fontWeight: 700, color }}>{value}</span>
  </div>
);

// ── Styles ─────────────────────────────────────────────────────────────────

const emptyStyle: React.CSSProperties = {
  padding: "2rem",
  textAlign: "center",
  color: "var(--text-muted)",
  backgroundColor: "#ffffff",
  borderRadius: "8px",
  border: "1px solid var(--border-subtle)",
};

const headerStyle: React.CSSProperties = {
  padding: "0.75rem 1rem",
  backgroundColor: "var(--bg-muted)",
  borderBottom: "1px solid var(--border-subtle)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "0.5rem",
};

const metricsGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(6, 1fr)",
  gap: "0.5rem",
  padding: "0.75rem 1rem",
  backgroundColor: "#fafafa",
  borderBottom: "1px solid var(--border-subtle)",
  fontSize: "0.78rem",
};

const sectionHeadingStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  fontWeight: 600,
  marginBottom: "0.4rem",
  color: "var(--text-primary)",
  display: "flex",
  alignItems: "center",
};

const pathListStyle: React.CSSProperties = {
  maxHeight: "140px",
  overflowY: "auto",
  display: "flex",
  flexDirection: "column",
  gap: "0.3rem",
};

const brokenPathRowStyle: React.CSSProperties = {
  fontSize: "0.74rem",
  padding: "0.35rem 0.5rem",
  backgroundColor: "#fff1f2",
  border: "1px solid #fecdd3",
  borderRadius: "4px",
  display: "flex",
  alignItems: "center",
  gap: "0.4rem",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const survivingPathRowStyle: React.CSSProperties = {
  fontSize: "0.74rem",
  padding: "0.35rem 0.5rem",
  backgroundColor: "#f0fdf4",
  border: "1px solid #bbf7d0",
  borderRadius: "4px",
  display: "flex",
  alignItems: "center",
  gap: "0.4rem",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const disclaimerStyle: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  backgroundColor: "#fffbeb",
  border: "1px solid #fde68a",
  borderRadius: "4px",
  fontSize: "0.71rem",
  color: "#78350f",
  display: "flex",
  alignItems: "flex-start",
  gap: "0.4rem",
};

const incompleteBadge: React.CSSProperties = {
  fontSize: "0.68rem",
  padding: "0.1rem 0.4rem",
  backgroundColor: "#fef3c7",
  border: "1px solid #fcd34d",
  borderRadius: "4px",
  color: "#92400e",
};

const toggleContainerStyle: React.CSSProperties = {
  display: "flex",
  backgroundColor: "#ffffff",
  padding: "0.15rem",
  borderRadius: "6px",
  border: "1px solid var(--border-subtle)",
};

function toggleBtnStyle(active: boolean, color: "blue" | "red"): React.CSSProperties {
  return {
    padding: "0.25rem 0.65rem",
    fontSize: "0.75rem",
    fontWeight: 600,
    borderRadius: "4px",
    border: "none",
    cursor: "pointer",
    backgroundColor: active ? (color === "blue" ? "var(--accent-blue)" : "#e11d48") : "transparent",
    color: active ? "#ffffff" : "var(--text-secondary)",
    transition: "all 0.15s ease",
  };
}
