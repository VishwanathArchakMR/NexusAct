import React, { useState, useEffect } from "react";
import type {
  InvestigationReport,
  ModuleSuggestion,
  SubgraphResponse,
  IngestionReport,
} from "../../types/investigation";
import {
  fetchModules,
  fetchSubgraph,
  runInvestigation,
  triggerIngestion,
} from "../../api/client";
import { GraphCanvas } from "./GraphCanvas";
import { AgentTrace } from "./AgentTrace";
import { ReviewerRankings } from "./ReviewerRankings";
import { CounterfactualDiff } from "./CounterfactualDiff";
import { IssueProposalCard } from "./IssueProposalCard";
import {
  Sparkles,
  GitBranch,
  ShieldCheck,
  Layers,
  Users,
  GitFork,
  FileText,
  Play,
  RotateCw,
} from "lucide-react";

export const InvestigationWorkspace: React.FC = () => {
  const [modules, setModules] = useState<ModuleSuggestion[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>("backend.app.graph.client");
  const [question, setQuestion] = useState<string>(
    "If I change this module, which other modules may be affected, who has relevant experience, what happens if the module is removed in a simulated graph, and can you create an issue explaining the findings?"
  );


  const [activeTab, setActiveTab] = useState<"graph" | "trace" | "reviewers" | "simulation" | "action">("graph");
  const [simulationView, setSimulationView] = useState<"baseline" | "scenario">("baseline");

  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [ingestionInfo, setIngestionInfo] = useState<IngestionReport | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadModules = async (q?: string) => {
    try {
      const data = await fetchModules(q, 100);
      setModules(data);
      if (data.length > 0 && !selectedModule) {
        setSelectedModule(data[0].id);
      }
    } catch (e) {
      console.warn("Could not load module suggestions:", e);
    }
  };

  const loadGraph = async (centerId?: string) => {
    try {
      const data = await fetchSubgraph(centerId, 2, 80);
      setSubgraph(data);
    } catch (e) {
      console.warn("Could not load subgraph:", e);
    }
  };

  // Load modules on mount
  useEffect(() => {
    loadModules();
    loadGraph();
  }, []);


  const handleIngest = async () => {
    setIsIngesting(true);
    setError(null);
    try {
      const res = await triggerIngestion();
      setIngestionInfo(res);
      await loadModules();
      await loadGraph(selectedModule);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setIsIngesting(false);
    }
  };

  const handleInvestigate = async () => {
    if (!selectedModule) return;
    setIsLoading(true);
    setError(null);
    try {
      const rep = await runInvestigation(question, selectedModule, 5);
      setReport(rep);
      await loadGraph(rep.target_module_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Investigation failed");
    } finally {
      setIsLoading(false);
    }
  };

  // Determine disrupted nodes/edges for counterfactual display
  const disappearedNodeIds =
    simulationView === "scenario" && report?.simulation_result
      ? [report.target_module_id, ...report.simulation_result.disconnected_modules]
      : [];

  const disappearedEdgeIds =
    simulationView === "scenario" && report?.simulation_result
      ? report.simulation_result.disappeared_paths.flatMap((p) => {
          const broken = p.broken_path;
          const edges: string[] = [];
          for (let i = 0; i < broken.length - 1; i++) {
            edges.push(`${broken[i]}->${broken[i + 1]}`);
          }
          return edges;
        })
      : [];

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "1.5rem 1rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* Search & Investigation Controls Card */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle)",
          padding: "1.25rem",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Sparkles size={18} color="var(--accent-blue)" />
              Graph Intelligence Engine
            </h2>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              Investigate code dependencies, simulate isolated module removal, identify reviewers, and propose actions.
            </p>
          </div>

          <button
            onClick={handleIngest}
            disabled={isIngesting}
            style={{
              padding: "0.45rem 0.85rem",
              fontSize: "0.78rem",
              fontWeight: 600,
              borderRadius: "6px",
              backgroundColor: "var(--bg-muted)",
              color: "var(--text-secondary)",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <RotateCw size={13} style={{ animation: isIngesting ? "spin 1.5s linear infinite" : undefined }} />
            {isIngesting ? "Ingesting Repository..." : "Sync Local Git Ingestion"}
          </button>
        </div>

        {ingestionInfo && (
          <div
            style={{
              backgroundColor: "var(--status-verified-bg)",
              border: "1px solid var(--status-verified-border)",
              borderRadius: "6px",
              padding: "0.5rem 0.75rem",
              fontSize: "0.76rem",
              color: "var(--status-verified-text)",
              marginBottom: "1rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>
              Ingested <strong>{ingestionInfo.repository_name}</strong>: {ingestionInfo.module_count} modules, {ingestionInfo.import_edge_count} dependency edges, {ingestionInfo.commit_count} commits.
            </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>SHA: {ingestionInfo.commit_sha.slice(0, 8)}</span>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: "0.75rem", alignItems: "flex-end" }}>
          {/* Target Module Selector */}
          <div>
            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>
              Target Module
            </label>
            <select
              value={selectedModule}
              onChange={(e) => {
                setSelectedModule(e.target.value);
                loadGraph(e.target.value);
              }}
              style={{
                width: "100%",
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.82rem",
                color: "var(--text-primary)",
                backgroundColor: "#ffffff",
                fontFamily: "var(--font-mono)",
              }}
            >
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Investigation Question Prompt */}
          <div>
            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>
              Investigation Prompt
            </label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask an architectural, impact, or reviewer question..."
              style={{
                width: "100%",
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.82rem",
                color: "var(--text-primary)",
                backgroundColor: "#ffffff",
              }}
            />
          </div>

          {/* Execute Investigation Button */}
          <button
            onClick={handleInvestigate}
            disabled={isLoading || !selectedModule}
            style={{
              padding: "0.55rem 1.25rem",
              fontSize: "0.82rem",
              fontWeight: 600,
              borderRadius: "6px",
              backgroundColor: "var(--accent-blue)",
              color: "#ffffff",
              border: "none",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              height: "38px",
            }}
          >
            <Play size={14} fill="#ffffff" />
            {isLoading ? "Investigating..." : "Investigate"}
          </button>
        </div>

        {error && (
          <div
            style={{
              marginTop: "0.75rem",
              padding: "0.5rem 0.75rem",
              backgroundColor: "var(--status-contradicted-bg)",
              border: "1px solid var(--status-contradicted-border)",
              borderRadius: "4px",
              color: "var(--status-contradicted-text)",
              fontSize: "0.78rem",
            }}
          >
            {error}
          </div>
        )}
      </div>

      {/* Verified Status Banner */}
      {report && (
        <div
          style={{
            backgroundColor: "#ffffff",
            borderRadius: "8px",
            border: "1px solid var(--border-subtle)",
            padding: "0.85rem 1.25rem",
            boxShadow: "var(--shadow-sm)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text-primary)" }}>
                {report.target_module_name}
              </span>
              {report.verification && (
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    padding: "0.15rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor:
                      report.verification.status === "VERIFIED"
                        ? "var(--status-verified-bg)"
                        : "var(--status-unknown-bg)",
                    color:
                      report.verification.status === "VERIFIED"
                        ? "var(--status-verified-text)"
                        : "var(--status-unknown-text)",
                    border: `1px solid ${
                      report.verification.status === "VERIFIED"
                        ? "var(--status-verified-border)"
                        : "var(--status-unknown-border)"
                    }`,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
                  }}
                >
                  <ShieldCheck size={12} />
                  {report.verification.status}
                </span>
              )}
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              {report.summary}
            </p>
          </div>

          <div style={{ display: "flex", gap: "1rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            <span>Tools Run: <strong>{report.budget_used}</strong></span>
            <span>Upstream Callers: <strong>{report.impact_result?.total_impacted_count ?? 0}</strong></span>
            <span>Disrupted Paths: <strong>{report.simulation_result?.disappeared_paths_count ?? 0}</strong></span>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-subtle)",
          gap: "0.5rem",
        }}
      >
        <button
          onClick={() => setActiveTab("graph")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "graph" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "graph" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <Layers size={14} />
          Dependency Graph
        </button>

        <button
          onClick={() => setActiveTab("trace")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "trace" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "trace" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <GitBranch size={14} />
          Agent MCP Trace {report ? `(${report.steps.length})` : ""}
        </button>

        <button
          onClick={() => setActiveTab("reviewers")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "reviewers" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "reviewers" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <Users size={14} />
          Reviewer Evidence {report?.reviewer_result ? `(${report.reviewer_result.candidates.length})` : ""}
        </button>

        <button
          onClick={() => setActiveTab("simulation")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "simulation" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "simulation" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <GitFork size={14} />
          Counterfactual Diff
        </button>

        <button
          onClick={() => setActiveTab("action")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "action" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "action" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <FileText size={14} />
          Verified Action
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "graph" && (
        <GraphCanvas
          data={subgraph}
          targetNodeId={selectedModule}
          disappearedNodeIds={disappearedNodeIds}
          disappearedEdgeIds={disappearedEdgeIds}
          isLoading={isLoading}
        />
      )}

      {activeTab === "trace" && (
        <AgentTrace
          steps={report?.steps ?? []}
          investigationId={report?.investigation_id}
        />
      )}

      {activeTab === "reviewers" && (
        <ReviewerRankings data={report?.reviewer_result ?? null} />
      )}

      {activeTab === "simulation" && (
        <CounterfactualDiff
          simulation={report?.simulation_result ?? null}
          activeView={simulationView}
          onToggleView={setSimulationView}
        />
      )}

      {activeTab === "action" && (
        <IssueProposalCard
          investigationId={report?.investigation_id ?? "inv_pending"}
          defaultTitle={report?.action_proposal?.title}
          defaultBody={report?.action_proposal?.body}
        />
      )}
    </div>
  );
};
