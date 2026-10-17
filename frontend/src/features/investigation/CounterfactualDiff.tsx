import React, { useState } from "react";
import type { SimulationResult, SimulationCandidate } from "../../types/investigation";
import { GitFork, AlertTriangle, CheckCircle2, Info, Play, Loader2 } from "lucide-react";

interface CounterfactualDiffProps {
  simulation: SimulationResult | null;
  activeView: "baseline" | "scenario";
  onToggleView: (view: "baseline" | "scenario") => void;
  candidates?: SimulationCandidate[];
  selectedCandidateId?: string;
  onSelectCandidate?: (moduleId: string) => void;
  onRunSimulation?: (moduleId: string) => void;
  isRunningSimulation?: boolean;
}

export const CounterfactualDiff: React.FC<CounterfactualDiffProps> = ({
  simulation,
  activeView,
  onToggleView,
  candidates = [],
  selectedCandidateId,
  onSelectCandidate,
  onRunSimulation,
  isRunningSimulation = false,
}) => {
  const [showSurviving, setShowSurviving] = useState(false);
  const [localSelectedMod, setLocalSelectedMod] = useState<string>(
    selectedCandidateId || (candidates.length > 0 ? candidates[0].id : "")
  );

  const handleModuleChange = (newMod: string) => {
    setLocalSelectedMod(newMod);
    if (onSelectCandidate) {
      onSelectCandidate(newMod);
    }
  };

  const handleRun = () => {
    const target = localSelectedMod || (candidates.length > 0 ? candidates[0].id : "");
    if (target && onRunSimulation) {
      onRunSimulation(target);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", width: "100%" }}>
      {/* ── Candidate Target Selection Bar ── */}
      <div
        style={{
          padding: "0.75rem 1rem",
          backgroundColor: "var(--bg-card, #ffffff)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle, #e2e8f0)",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.75rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flex: 1, minWidth: "260px" }}>
          <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary, #0f172a)", whiteSpace: "nowrap" }}>
            Candidate Module:
          </label>
          <select
            value={localSelectedMod}
            onChange={(e) => handleModuleChange(e.target.value)}
            disabled={isRunningSimulation || candidates.length === 0}
            style={{
              flex: 1,
              padding: "0.4rem 0.6rem",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #cbd5e1)",
              backgroundColor: "#ffffff",
              fontSize: "0.8rem",
              color: "var(--text-primary, #0f172a)",
              outline: "none",
            }}
          >
            {candidates.length === 0 ? (
              <option value="">No candidate modules in graph</option>
            ) : (
              candidates.map((cand) => (
                <option key={cand.id} value={cand.id}>
                  {cand.name} (callers: {cand.in_degree}, deps: {cand.out_degree})
                </option>
              ))
            )}
          </select>
        </div>

        <button
          onClick={handleRun}
          disabled={isRunningSimulation || candidates.length === 0}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            padding: "0.45rem 0.9rem",
            borderRadius: "6px",
            backgroundColor: isRunningSimulation || candidates.length === 0 ? "#94a3b8" : "var(--accent-blue, #2563eb)",
            color: "#ffffff",
            border: "none",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: isRunningSimulation || candidates.length === 0 ? "not-allowed" : "pointer",
            transition: "all 0.15s ease",
          }}
        >
          {isRunningSimulation ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span>Cloning Graph & Simulating...</span>
            </>
          ) : (
            <>
              <Play size={14} />
              <span>Run Counterfactual Simulation</span>
            </>
          )}
        </button>
      </div>

      {/* ── Simulation Results Area ── */}
      {!simulation ? (
        <div style={emptyStyle}>
          <GitFork size={32} color="var(--accent-blue, #2563eb)" style={{ marginBottom: "0.5rem" }} />
          <h4 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-primary, #0f172a)", marginBottom: "0.25rem" }}>
            Awaiting Counterfactual Simulation
          </h4>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary, #475569)", maxWidth: "520px", lineHeight: 1.4 }}>
            Select an active module above and click <strong>Run Counterfactual Simulation</strong>. FalkorDB will clone the active graph into an isolated scenario sandbox, excise the target component, compare all before-and-after routes, and calculate blast radius without modifying production data.
          </p>
        </div>
      ) : (
        <div style={{ backgroundColor: "var(--bg-card, #ffffff)", borderRadius: "8px", border: "1px solid var(--border-subtle, #e2e8f0)", overflow: "hidden" }}>
          {/* Header */}
          <div style={headerStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <GitFork size={16} color="var(--accent-blue, #2563eb)" />
              <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary, #0f172a)" }}>
                Counterfactual Simulation — Removed:{" "}
                <code style={{ fontFamily: "var(--font-mono, monospace)", color: "#e11d48", fontWeight: 700 }}>
                  {simulation.target_module_name || simulation.target_module_id}
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

          {/* Metrics Row */}
          {(() => {
            const blastPct = ((simulation.blast_radius_score ?? 0) * 100).toFixed(1);
            const disappearedPaths = simulation.disappeared_paths ?? [];
            const survivingPaths = simulation.surviving_paths ?? [];
            const isolatedModules = simulation.newly_isolated_modules ?? [];

            return (
              <>
                <div style={metricsGridStyle}>
                  <MetricCard
                    label="Baseline Paths"
                    value={simulation.baseline_paths_count}
                    color="var(--text-secondary, #475569)"
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
                    title="broken_paths / baseline_paths_count — fraction of known upstream paths disrupted."
                  />
                  <MetricCard
                    label="Surviving Modules"
                    value={simulation.surviving_modules_count}
                    color="var(--text-secondary, #475569)"
                    title="Total Module nodes remaining in scenario copy"
                  />
                </div>

                {/* Zero Impact Banner */}
                {simulation.baseline_paths_count === 0 && (
                  <div
                    style={{
                      margin: "0.75rem 1rem",
                      padding: "0.6rem 0.85rem",
                      borderRadius: "6px",
                      backgroundColor: "#f8fafc",
                      border: "1px solid var(--border-subtle, #e2e8f0)",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      fontSize: "0.78rem",
                      color: "var(--text-secondary, #475569)",
                    }}
                  >
                    <Info size={15} color="var(--accent-blue, #2563eb)" />
                    <span>
                      <strong>Grounded zero-impact finding:</strong> The excised module has zero upstream callers in this snapshot. No dependency routes traversed it, confirming 0% architectural blast radius.
                    </span>
                  </div>
                )}

                {/* Newly Isolated Modules */}
                {isolatedModules.length > 0 && (
                  <div
                    style={{
                      margin: "0.75rem 1rem",
                      padding: "0.65rem 0.85rem",
                      borderRadius: "6px",
                      backgroundColor: "rgba(225, 29, 72, 0.06)",
                      border: "1px solid rgba(225, 29, 72, 0.2)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.35rem",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.78rem", fontWeight: 600, color: "#e11d48" }}>
                      <AlertTriangle size={14} />
                      <span>Newly Isolated Modules ({isolatedModules.length})</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                      {isolatedModules.map((modId) => (
                        <span
                          key={modId}
                          style={{
                            fontFamily: "var(--font-mono, monospace)",
                            fontSize: "0.72rem",
                            backgroundColor: "#ffffff",
                            border: "1px solid rgba(225, 29, 72, 0.3)",
                            borderRadius: "4px",
                            padding: "0.15rem 0.4rem",
                            color: "#be123c",
                          }}
                        >
                          {modId}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Disappeared Broken Paths List */}
                {disappearedPaths.length > 0 && (
                  <div style={{ padding: "0.75rem 1rem", borderTop: "1px solid var(--border-subtle, #e2e8f0)" }}>
                    <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#e11d48", marginBottom: "0.5rem" }}>
                      Disrupted Dependency Routes ({disappearedPaths.length})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                      {disappearedPaths.slice(0, 10).map((dp, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: "0.5rem 0.75rem",
                            backgroundColor: "#fff1f2",
                            border: "1px solid #ffe4e6",
                            borderRadius: "6px",
                            fontSize: "0.75rem",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <span style={{ fontWeight: 600, color: "#9f1239" }}>
                            {dp.dependent_module_name}
                          </span>
                          <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#e11d48" }}>
                            {dp.broken_path ? dp.broken_path.join(" → ") : `${dp.hops} hops`}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Surviving Paths Toggle */}
                {survivingPaths.length > 0 && (
                  <div style={{ padding: "0.75rem 1rem", borderTop: "1px solid var(--border-subtle, #e2e8f0)" }}>
                    <button
                      onClick={() => setShowSurviving(!showSurviving)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        color: "#16a34a",
                        padding: 0,
                      }}
                    >
                      <CheckCircle2 size={14} />
                      <span>
                        {showSurviving ? "Hide" : "Show"} Surviving Alternate Routes ({survivingPaths.length})
                      </span>
                    </button>

                    {showSurviving && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "0.5rem" }}>
                        {survivingPaths.slice(0, 8).map((sp, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: "0.45rem 0.65rem",
                              backgroundColor: "#f0fdf4",
                              border: "1px solid #dcfce7",
                              borderRadius: "6px",
                              fontSize: "0.75rem",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <span style={{ fontWeight: 600, color: "#166534" }}>{sp.dependent_module_name}</span>
                            <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#15803d" }}>
                              {sp.surviving_path ? sp.surviving_path.join(" → ") : `${sp.hops} hops`}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {/* Disclaimer */}
                <div
                  style={{
                    padding: "0.6rem 1rem",
                    borderTop: "1px solid var(--border-subtle, #e2e8f0)",
                    backgroundColor: "var(--bg-muted, #f8fafc)",
                    fontSize: "0.72rem",
                    color: "var(--text-muted, #64748b)",
                    fontStyle: "italic",
                  }}
                >
                  {simulation.disclaimer || "Simulation prediction is derived from static dependency topology."}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
};

// ── Internal Helper Components & Styles ───────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string | number;
  color: string;
  title?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, color, title }) => (
  <div style={metricCardStyle} title={title}>
    <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #64748b)" }}>{label}</div>
    <div style={{ fontSize: "1.2rem", fontWeight: 700, color, marginTop: "0.15rem" }}>{value}</div>
  </div>
);

const emptyStyle: React.CSSProperties = {
  padding: "2rem 1.5rem",
  textAlign: "center",
  backgroundColor: "var(--bg-card, #ffffff)",
  borderRadius: "8px",
  border: "1px solid var(--border-subtle, #e2e8f0)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
};

const headerStyle: React.CSSProperties = {
  padding: "0.75rem 1rem",
  backgroundColor: "var(--bg-muted, #f8fafc)",
  borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "0.5rem",
};

const toggleContainerStyle: React.CSSProperties = {
  display: "flex",
  backgroundColor: "#ffffff",
  border: "1px solid var(--border-subtle, #cbd5e1)",
  borderRadius: "6px",
  overflow: "hidden",
};

const toggleBtnStyle = (active: boolean, color: "blue" | "red"): React.CSSProperties => ({
  padding: "0.3rem 0.75rem",
  fontSize: "0.75rem",
  fontWeight: active ? 700 : 500,
  border: "none",
  backgroundColor: active
    ? color === "blue"
      ? "var(--accent-blue, #2563eb)"
      : "#e11d48"
    : "transparent",
  color: active ? "#ffffff" : "var(--text-secondary, #475569)",
  cursor: "pointer",
  transition: "all 0.15s ease",
});

const metricsGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
  gap: "0.5rem",
  padding: "0.75rem 1rem",
};

const metricCardStyle: React.CSSProperties = {
  backgroundColor: "var(--bg-muted, #f8fafc)",
  borderRadius: "6px",
  padding: "0.6rem 0.75rem",
  border: "1px solid var(--border-subtle, #e2e8f0)",
  textAlign: "center",
};

const incompleteBadge: React.CSSProperties = {
  fontSize: "0.68rem",
  fontWeight: 600,
  color: "#d97706",
  backgroundColor: "#fef3c7",
  border: "1px solid #fde68a",
  borderRadius: "4px",
  padding: "0.15rem 0.4rem",
};
