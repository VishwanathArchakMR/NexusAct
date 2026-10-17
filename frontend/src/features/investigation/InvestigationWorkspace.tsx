import React, { useState, useEffect } from "react";
import type {
  InvestigationReport,
  ModuleSuggestion,
  SubgraphResponse,
  IngestionReport,
  RepositoryRecord,
  SourceMetadataOutput,
  SourceSnapshot,
} from "../../types/investigation";
import {
  fetchModules,
  fetchSubgraph,
  runInvestigation,
  triggerIngestion,
  fetchRepositories,
  cloneAndIngest,
  refreshRepository,
  fetchSourceMetadata,
  fetchRepositorySnapshot,
} from "../../api/client";

import { GraphCanvas } from "./GraphCanvas";
import { AgentTrace } from "./AgentTrace";
import { ReviewerRankings } from "./ReviewerRankings";
import { CounterfactualDiff } from "./CounterfactualDiff";
import { IssueProposalCard } from "./IssueProposalCard";
import { CodeInspector } from "./CodeInspector";

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
  FolderGit2,
  AlertTriangle,
  HelpCircle,
  Plus,
  Network,
  Compass,
  Code,
  ShieldAlert,
  DollarSign,
  CheckCircle2,
  FileCode,
} from "lucide-react";

export interface InvestigationWorkspaceProps {
  selectedRepoId?: string;
  onSelectRepoId?: (id: string) => void;
}

export type InvestigationMode =
  | "codebase_walkthrough"
  | "change_impact"
  | "security_triage"
  | "fraud_demo";

export const InvestigationWorkspace: React.FC<InvestigationWorkspaceProps> = ({
  selectedRepoId: propRepoId,
  onSelectRepoId,
}) => {
  // Repositories state
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>(propRepoId || "repo:local_nexusact");
  const [sourceMetadata, setSourceMetadata] = useState<SourceMetadataOutput | null>(null);
  const [snapshot, setSnapshot] = useState<SourceSnapshot | null>(null);
  const [isCheckingFreshness, setIsCheckingFreshness] = useState<boolean>(false);

  const [prevPropRepoId, setPrevPropRepoId] = useState(propRepoId);
  if (propRepoId && propRepoId !== prevPropRepoId) {
    setPrevPropRepoId(propRepoId);
    setSelectedRepoId(propRepoId);
  }

  // Investigation Mode
  const [investigationMode, setInvestigationMode] = useState<InvestigationMode>("codebase_walkthrough");

  // Onboard repository modal state
  const [showOnboardModal, setShowOnboardModal] = useState<boolean>(false);
  const [onboardType, setOnboardType] = useState<"github" | "local">("github");
  const [onboardUrlOrPath, setOnboardUrlOrPath] = useState<string>("");
  const [onboardDisplayName, setOnboardDisplayName] = useState<string>("");
  const [isOnboarding, setIsOnboarding] = useState<boolean>(false);
  const [onboardError, setOnboardError] = useState<string | null>(null);

  // Investigation state
  const [modules, setModules] = useState<ModuleSuggestion[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>("");
  const [question, setQuestion] = useState<string>(
    "How do API requests flow into the graph storage layer, and what symbols are defined?"
  );

  const [activeTab, setActiveTab] = useState<
    | "graph"
    | "code"
    | "security"
    | "fraud"
    | "simulation"
    | "reviewers"
    | "trace"
    | "neighborhood"
    | "provenance"
    | "action"
  >("graph");
  const [simulationView, setSimulationView] = useState<"baseline" | "scenario">("baseline");

  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [ingestionInfo, setIngestionInfo] = useState<IngestionReport | null>(null);


  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRepositories = React.useCallback(async () => {
    try {
      const repos = await fetchRepositories();
      setRepositories(repos);
      if (repos.length > 0) {
        setSelectedRepoId((prev) => (repos.some((r) => r.id === prev) ? prev : repos[0].id));
      }
    } catch (e) {
      console.warn("Could not load repositories:", e);
    }
  }, []);

  const loadSnapshot = React.useCallback(async (repoId: string, refresh = false) => {
    try {
      setIsCheckingFreshness(true);
      const snap = await fetchRepositorySnapshot(repoId, refresh);
      setSnapshot(snap);
    } catch (e) {
      console.warn("Could not load repository snapshot:", e);
    } finally {
      setIsCheckingFreshness(false);
    }
  }, []);

  const loadRepoMetadata = React.useCallback(async (repoId: string) => {
    try {
      const meta = await fetchSourceMetadata(repoId);
      setSourceMetadata(meta);
    } catch {
      setSourceMetadata(null);
    }
  }, []);

  const loadModules = React.useCallback(async (q?: string, repoId?: string) => {
    try {
      const activeRepo = repoId || selectedRepoId;
      const data = await fetchModules(q, 100, activeRepo);
      setModules(data);
    } catch (e) {
      console.warn("Could not load module suggestions:", e);
    }
  }, [selectedRepoId]);

  const loadGraph = React.useCallback(async (centerId?: string, repoId?: string) => {
    try {
      const activeRepo = repoId || selectedRepoId;
      const data = await fetchSubgraph(centerId, 2, 80, activeRepo);
      setSubgraph(data);
    } catch (e) {
      console.warn("Could not load subgraph:", e);
    }
  }, [selectedRepoId]);

  useEffect(() => {
    (async () => { await loadRepositories(); })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadRepositories]);

  useEffect(() => {
    if (selectedRepoId) {
      setReport(null);
      setSelectedModule("");
      setError(null);
      (async () => {
        await Promise.all([
          loadSnapshot(selectedRepoId),
          loadRepoMetadata(selectedRepoId),
          loadModules(undefined, selectedRepoId),
          loadGraph(undefined, selectedRepoId),
        ]);
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepoId, loadSnapshot, loadRepoMetadata, loadModules, loadGraph]);


  const handleRefresh = async () => {
    if (!selectedRepoId) return;
    setIsRefreshing(true);
    setError(null);
    try {
      let res: IngestionReport;
      if (selectedRepoId === "repo:local_nexusact") {
        res = await triggerIngestion();
      } else {
        res = await refreshRepository(selectedRepoId);
      }
      setIngestionInfo(res);
      await loadRepositories();
      await loadSnapshot(selectedRepoId, true);
      await loadRepoMetadata(selectedRepoId);
      await loadModules(undefined, selectedRepoId);
      await loadGraph(undefined, selectedRepoId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleModeChange = (mode: InvestigationMode) => {
    setInvestigationMode(mode);
    setError(null);

    if (mode === "codebase_walkthrough") {
      setQuestion("How do API requests flow into the graph storage layer, and what symbols are defined?");
      setActiveTab("graph");
    } else if (mode === "change_impact") {
      setQuestion("What might be affected if I modify the graph client, and who has relevant experience?");
      setActiveTab("graph");
    } else if (mode === "security_triage") {
      setQuestion("Check dependencies for security advisories and trace if vulnerable packages are reachable from our code.");
      setActiveTab("security");
    } else if (mode === "fraud_demo") {
      setQuestion("Detect circular money movement loops and shared device fraud indicators across accounts.");
      setActiveTab("fraud");
    }
  };

  const handleOnboardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onboardUrlOrPath.trim()) return;

    setIsOnboarding(true);
    setOnboardError(null);
    try {
      const res = await cloneAndIngest({
        url_or_path: onboardUrlOrPath.trim(),
        source_type: onboardType,
        display_name: onboardDisplayName.trim() || undefined,
      });

      setIngestionInfo(res);
      await loadRepositories();

      if (res.repository_id) {
        setSelectedRepoId(res.repository_id);
      }

      setShowOnboardModal(false);
      setOnboardUrlOrPath("");
      setOnboardDisplayName("");
    } catch (err) {
      setOnboardError(err instanceof Error ? err.message : "Repository onboarding failed");
    } finally {
      setIsOnboarding(false);
    }
  };

  const handleInvestigate = async (targetOverride?: string) => {
    const target = targetOverride !== undefined ? targetOverride : selectedModule;
    setIsLoading(true);
    setError(null);
    try {
      const rep = await runInvestigation(
        question,
        target.trim() ? target.trim() : null,
        selectedRepoId,
        5,
        investigationMode
      );
      setReport(rep);
      if (rep.target_module_id) {
        setSelectedModule(rep.target_module_id);
        await loadGraph(rep.target_module_id, selectedRepoId);
      }
      if (rep.source_snapshot) {
        setSnapshot(rep.source_snapshot);
      }

      // Auto-switch to corresponding tab
      if (rep.security_triage_result || investigationMode === "security_triage") {
        setActiveTab("security");
      } else if (rep.fraud_result || investigationMode === "fraud_demo") {
        setActiveTab("fraud");
      } else if (rep.simulation_result) {
        setActiveTab("graph");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Investigation failed");
      setReport(null);
    } finally {
      setIsLoading(false);
    }
  };

  const activeRepo = repositories.find((r) => r.id === selectedRepoId);

  // Determine disrupted and surviving nodes/edges for counterfactual display
  const sim = report?.simulation_result ?? null;

  const disappearedNodeIds: string[] =
    simulationView === "scenario" && sim
      ? [sim.target_module_id, ...sim.newly_isolated_modules]
      : [];

  const disappearedEdgeIds: string[] =
    simulationView === "scenario" && sim
      ? sim.disappeared_paths.flatMap((p) => {
          const edges: string[] = [];
          for (let i = 0; i < p.broken_path.length - 1; i++) {
            edges.push(`${p.broken_path[i]}->${p.broken_path[i + 1]}`);
          }
          return edges;
        })
      : [];

  const survivingNodeIds: string[] =
    simulationView === "scenario" && sim
      ? Array.from(new Set(sim.surviving_paths.flatMap((p) => p.surviving_path)))
      : [];

  const activePathNodes: string[] = React.useMemo(() => {
    if (report?.shortest_path_result?.path_nodes && report.shortest_path_result.path_nodes.length > 0) {
      return report.shortest_path_result.path_nodes;
    }
    if (report?.impact_result?.impacted_modules) {
      const multiHop = report.impact_result.impacted_modules.find((m) => m.path && m.path.length >= 2);
      if (multiHop) return multiHop.path;
    }
    return [];
  }, [report]);

  return (
    <div style={{ maxWidth: "1320px", margin: "0 auto", padding: "1.5rem 1rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* ── Top Canonical Source & Freshness Bar ── */}
      <div
        style={{
          backgroundColor: "var(--bg-card)",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle)",
          padding: "1rem 1.25rem",
          boxShadow: "var(--shadow-sm)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <FolderGit2 size={20} color="var(--accent-blue)" />
            <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary)" }}>
              Repository:
            </span>
          </div>

          <select
            value={selectedRepoId}
            onChange={(e) => {
              const newId = e.target.value;
              setSelectedRepoId(newId);
              onSelectRepoId?.(newId);
              setReport(null);
              setSelectedModule("");
              setError(null);
            }}
            style={{
              padding: "0.45rem 0.85rem",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle)",
              fontSize: "0.82rem",
              fontWeight: 600,
              backgroundColor: "var(--bg-muted)",
              color: "var(--text-primary)",
              cursor: "pointer",
            }}
          >
            {repositories.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.source_type === "github" ? "GitHub" : "Local"} • {r.commit_sha.slice(0, 7)})
              </option>
            ))}
          </select>

          {/* Freshness Badge */}
          {snapshot && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  fontSize: "0.74rem",
                  fontWeight: 700,
                  padding: "0.2rem 0.6rem",
                  borderRadius: "20px",
                  backgroundColor:
                    snapshot.freshness_status === "FRESH"
                      ? "#dcfce7"
                      : snapshot.freshness_status === "UPDATED"
                      ? "#dbeafe"
                      : "#fef3c7",
                  color:
                    snapshot.freshness_status === "FRESH"
                      ? "#15803d"
                      : snapshot.freshness_status === "UPDATED"
                      ? "#1d4ed8"
                      : "#b45309",
                  border: `1px solid ${
                    snapshot.freshness_status === "FRESH"
                      ? "#86efac"
                      : snapshot.freshness_status === "UPDATED"
                      ? "#93c5fd"
                      : "#fde68a"
                  }`,
                }}
              >
                {snapshot.freshness_status === "FRESH" ? (
                  <CheckCircle2 size={13} />
                ) : snapshot.freshness_status === "UPDATED" ? (
                  <RotateCw size={13} />
                ) : (
                  <AlertTriangle size={13} />
                )}
                {snapshot.freshness_status}
              </span>

              {snapshot.working_tree_fingerprint && (
                <span
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.2rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor: "var(--bg-muted)",
                    color: "var(--text-secondary)",
                    fontFamily: "var(--font-mono)",
                  }}
                  title="Deterministic SHA-256 fingerprint of repository working-tree source files"
                >
                  fp:{snapshot.working_tree_fingerprint.slice(0, 10)}
                </span>
              )}

              <span
                style={{
                  fontSize: "0.72rem",
                  padding: "0.2rem 0.5rem",
                  borderRadius: "4px",
                  backgroundColor: "var(--bg-muted)",
                  color: "var(--text-secondary)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                rev:{snapshot.commit_sha.slice(0, 8)}
              </span>
            </div>
          )}

          {activeRepo && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              <span style={{ padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: "var(--bg-muted)", fontFamily: "var(--font-mono)" }}>
                Graph: {activeRepo.graph_name}
              </span>
              <span>Modules: <strong>{activeRepo.module_count}</strong></span>
              <span>Edges: <strong>{activeRepo.edge_count}</strong></span>
            </div>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            onClick={() => loadSnapshot(selectedRepoId, true)}
            disabled={isCheckingFreshness}
            title="Check upstream git freshness and local fingerprint"
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
              cursor: "pointer",
            }}
          >
            <RotateCw size={13} style={{ animation: isCheckingFreshness ? "spin 1.5s linear infinite" : undefined }} />
            {isCheckingFreshness ? "Checking..." : "Verify Freshness"}
          </button>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Re-ingest repository to latest revision"
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
              cursor: "pointer",
            }}
          >
            <RotateCw size={13} style={{ animation: isRefreshing ? "spin 1.5s linear infinite" : undefined }} />
            {isRefreshing ? "Refreshing..." : "Re-Ingest"}
          </button>

          <button
            onClick={() => setShowOnboardModal(true)}
            style={{
              padding: "0.45rem 0.85rem",
              fontSize: "0.78rem",
              fontWeight: 600,
              borderRadius: "6px",
              backgroundColor: "var(--accent-blue)",
              color: "#ffffff",
              border: "none",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              cursor: "pointer",
            }}
          >
            <Plus size={14} />
            Onboard Repo
          </button>
        </div>
      </div>

      {/* ── Three Application Workflows Mode Bar ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "0.75rem",
        }}
      >
        {/* Workflow 1: Codebase Walkthrough */}
        <div
          onClick={() => handleModeChange("codebase_walkthrough")}
          style={{
            padding: "0.85rem 1rem",
            borderRadius: "8px",
            border: `2px solid ${
              investigationMode === "codebase_walkthrough"
                ? "var(--accent-blue)"
                : "var(--border-subtle)"
            }`,
            backgroundColor:
              investigationMode === "codebase_walkthrough"
                ? "var(--accent-blue-subtle)"
                : "var(--bg-card)",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.86rem", color: "var(--text-primary)" }}>
              <Code size={16} color="var(--accent-blue)" />
              Codebase Walkthrough
            </span>
            {investigationMode === "codebase_walkthrough" && (
              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--accent-blue)" }}>ACTIVE</span>
            )}
          </div>
          <span style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
            Explore request flows, architecture, symbol references, and live code preview.
          </span>
        </div>

        {/* Workflow 2: Change Impact & Reviewers */}
        <div
          onClick={() => handleModeChange("change_impact")}
          style={{
            padding: "0.85rem 1rem",
            borderRadius: "8px",
            border: `2px solid ${
              investigationMode === "change_impact"
                ? "#6366f1"
                : "var(--border-subtle)"
            }`,
            backgroundColor:
              investigationMode === "change_impact"
                ? "rgba(99, 102, 241, 0.08)"
                : "var(--bg-card)",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.86rem", color: "var(--text-primary)" }}>
              <Layers size={16} color="#6366f1" />
              Change Impact & Reviewers
            </span>
            {investigationMode === "change_impact" && (
              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "#6366f1" }}>ACTIVE</span>
            )}
          </div>
          <span style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
            Trace blast radius, counterfactual disruption in cloned graph, and commit owner discovery.
          </span>
        </div>

        {/* Workflow 3: Security Triage (OSV) */}
        <div
          onClick={() => handleModeChange("security_triage")}
          style={{
            padding: "0.85rem 1rem",
            borderRadius: "8px",
            border: `2px solid ${
              investigationMode === "security_triage"
                ? "#ef4444"
                : "var(--border-subtle)"
            }`,
            backgroundColor:
              investigationMode === "security_triage"
                ? "rgba(239, 68, 68, 0.08)"
                : "var(--bg-card)",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.86rem", color: "var(--text-primary)" }}>
              <ShieldAlert size={16} color="#ef4444" />
              Security Triage (OSV)
            </span>
            {investigationMode === "security_triage" && (
              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "#ef4444" }}>ACTIVE</span>
            )}
          </div>
          <span style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
            Inspect dependency manifests against OSV.dev advisories and trace module reachability.
          </span>
        </div>

        {/* Workflow 4: Fraud Pattern Demo */}
        <div
          onClick={() => handleModeChange("fraud_demo")}
          style={{
            padding: "0.85rem 1rem",
            borderRadius: "8px",
            border: `2px solid ${
              investigationMode === "fraud_demo"
                ? "#d97706"
                : "var(--border-subtle)"
            }`,
            backgroundColor:
              investigationMode === "fraud_demo"
                ? "rgba(217, 119, 6, 0.08)"
                : "var(--bg-card)",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.86rem", color: "var(--text-primary)" }}>
              <DollarSign size={16} color="#d97706" />
              Fraud Topology Demo
            </span>
            {investigationMode === "fraud_demo" && (
              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "#d97706" }}>ACTIVE</span>
            )}
          </div>
          <span style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
            Synthetic financial graph: circular routing cycles, shared devices, and benign controls.
          </span>
        </div>
      </div>

      {/* Disclosed Gaps & Warnings Strip */}
      {activeRepo && (activeRepo.known_gaps?.length > 0 || activeRepo.parser_warnings?.length > 0) && (
        <div
          style={{
            backgroundColor: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: "6px",
            padding: "0.5rem 0.85rem",
            fontSize: "0.76rem",
            color: "#92400e",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700 }}>
            <AlertTriangle size={14} color="#d97706" />
            Source Provenance & Evidence Disclosures:
          </div>
          <ul style={{ margin: "0.2rem 0 0 1.2rem", padding: 0 }}>
            {activeRepo.known_gaps?.map((gap, idx) => (
              <li key={`gap-${idx}`}>{gap}</li>
            ))}
            {activeRepo.parser_warnings?.map((warn, idx) => (
              <li key={`warn-${idx}`}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Onboard Repository Modal */}
      {showOnboardModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              width: "100%",
              maxWidth: "520px",
              padding: "1.5rem",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                Onboard Repository into NexusAct
              </h3>
              <button
                onClick={() => setShowOnboardModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleOnboardSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.4rem" }}>
                  Source Origin
                </label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setOnboardType("github")}
                    style={{
                      flex: 1,
                      padding: "0.5rem",
                      borderRadius: "6px",
                      border: `1px solid ${onboardType === "github" ? "var(--accent-blue)" : "var(--border-subtle)"}`,
                      backgroundColor: onboardType === "github" ? "var(--accent-blue-subtle)" : "var(--bg-card)",
                      color: onboardType === "github" ? "var(--accent-blue)" : "var(--text-secondary)",
                      fontWeight: 600,
                      fontSize: "0.8rem",
                      cursor: "pointer",
                    }}
                  >
                    Public GitHub URL
                  </button>
                  <button
                    type="button"
                    onClick={() => setOnboardType("local")}
                    style={{
                      flex: 1,
                      padding: "0.5rem",
                      borderRadius: "6px",
                      border: `1px solid ${onboardType === "local" ? "var(--accent-blue)" : "var(--border-subtle)"}`,
                      backgroundColor: onboardType === "local" ? "var(--accent-blue-subtle)" : "var(--bg-card)",
                      color: onboardType === "local" ? "var(--accent-blue)" : "var(--text-secondary)",
                      fontWeight: 600,
                      fontSize: "0.8rem",
                      cursor: "pointer",
                    }}
                  >
                    Local Filesystem Path
                  </button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.4rem" }}>
                  {onboardType === "github" ? "GitHub HTTPS URL" : "Local Absolute Path"}
                </label>
                <input
                  type="text"
                  required
                  value={onboardUrlOrPath}
                  onChange={(e) => setOnboardUrlOrPath(e.target.value)}
                  placeholder={
                    onboardType === "github"
                      ? "https://github.com/owner/repository"
                      : "c:\\path\\to\\git\\repository"
                  }
                  style={{
                    width: "100%",
                    padding: "0.55rem 0.75rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border-subtle)",
                    fontSize: "0.82rem",
                    color: "var(--text-primary)",
                  }}
                />
                <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.2rem", display: "block" }}>
                  {onboardType === "github"
                    ? "Safe, bounded HTTPS clone into ~/.cache/nexusact. No arbitrary shell execution."
                    : "Inspects local Git repository tree, AST dependencies, and commit log."}
                </span>
              </div>

              <div>
                <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.4rem" }}>
                  Display Name (Optional)
                </label>
                <input
                  type="text"
                  value={onboardDisplayName}
                  onChange={(e) => setOnboardDisplayName(e.target.value)}
                  placeholder="e.g. My Production Service"
                  style={{
                    width: "100%",
                    padding: "0.55rem 0.75rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border-subtle)",
                    fontSize: "0.82rem",
                    color: "var(--text-primary)",
                  }}
                />
              </div>

              {onboardError && (
                <div style={{ padding: "0.5rem", borderRadius: "6px", backgroundColor: "#fee2e2", color: "#b91c1c", fontSize: "0.78rem" }}>
                  {onboardError}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => setShowOnboardModal(false)}
                  style={{
                    padding: "0.5rem 1rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border-subtle)",
                    backgroundColor: "var(--bg-card)",
                    color: "var(--text-primary)",
                    fontSize: "0.82rem",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isOnboarding}
                  style={{
                    padding: "0.5rem 1.25rem",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: "var(--accent-blue)",
                    color: "#ffffff",
                    fontWeight: 600,
                    fontSize: "0.82rem",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                  }}
                >
                  <RotateCw size={13} style={{ animation: isOnboarding ? "spin 1.5s linear infinite" : undefined }} />
                  {isOnboarding ? "Cloning & Ingesting..." : "Ingest Repository"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Investigation Controls Card ── */}
      <div
        style={{
          backgroundColor: "var(--bg-card)",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle)",
          padding: "1.25rem",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div style={{ marginBottom: "1rem" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Sparkles size={18} color="var(--accent-blue)" />
            Dynamic Graph Intelligence Investigation: {
              investigationMode === "codebase_walkthrough"
                ? "Codebase Walkthrough & Symbol Inspection"
                : investigationMode === "change_impact"
                ? "Dynamic Graph Impact & Reviewer Analysis"
                : investigationMode === "security_triage"
                ? "OSV Vulnerability Triage & Reachability Trace"
                : "Synthetic Financial Graph Fraud Topology"
            }
          </h2>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
            NexusAct binds every investigation to an authoritative SourceSnapshot, verifies topological paths in FalkorDB, and executes adaptive MCP tools.
          </p>
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

        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: "0.75rem", alignItems: "flex-end" }}>
          {/* Investigation Question Prompt */}
          <div>
            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>
              Natural-Language Investigation Question
            </label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Which modules depend on the database layer? Who knows about authentication?"
              style={{
                width: "100%",
                padding: "0.55rem 0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.82rem",
                color: "var(--text-primary)",
                backgroundColor: "var(--bg-card)",
              }}
            />
          </div>

          {/* Target Module Selector */}
          <div>
            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>
              Target Focus (Optional)
            </label>
            <select
              value={selectedModule}
              onChange={(e) => {
                setSelectedModule(e.target.value);
                if (e.target.value) {
                  loadGraph(e.target.value, selectedRepoId);
                }
              }}
              style={{
                width: "100%",
                padding: "0.55rem 0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.82rem",
                color: "var(--text-primary)",
                backgroundColor: "var(--bg-card)",
                fontFamily: "var(--font-mono)",
              }}
            >
              <option value="">Auto-resolve from prompt</option>
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Execute Investigation Button */}
          <button
            onClick={() => handleInvestigate()}
            disabled={isLoading || !question.trim()}
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
              cursor: "pointer",
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

      {/* Ambiguity Clarification Modal/Banner */}
      {report?.status === "AMBIGUOUS" && (
        <div
          style={{
            backgroundColor: "#fffbeb",
            borderRadius: "8px",
            border: "1px solid #fde68a",
            padding: "1rem 1.25rem",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#92400e", fontWeight: 700, fontSize: "0.88rem" }}>
            <HelpCircle size={18} color="#d97706" />
            Target Unresolved in Selected Repository Graph
          </div>
          <p style={{ margin: "0.2rem 0 0.5rem 0" }}>{report.unresolved_reason || report.summary}</p>
          {report.ambiguity_candidates && report.ambiguity_candidates.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#78350f" }}>
                Available candidate modules in this graph:
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.3rem" }}>
                {report.ambiguity_candidates.map((c) => (
                  <button
                    key={c.module_id}
                    onClick={() => {
                      setSelectedModule(c.module_id);
                      handleInvestigate(c.module_id);
                    }}
                    style={{
                      padding: "0.3rem 0.6rem",
                      fontSize: "0.75rem",
                      borderRadius: "4px",
                      border: "1px solid #d97706",
                      backgroundColor: "var(--bg-card)",
                      cursor: "pointer",
                      fontWeight: 600,
                      color: "#d97706",
                    }}
                  >
                    {c.module_name || c.module_id}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Historical Report Notice if report belongs to a different repository */}
      {report && report.repository_id && report.repository_id !== selectedRepoId && (
        <div
          style={{
            padding: "0.6rem 1rem",
            backgroundColor: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: "6px",
            fontSize: "0.78rem",
            color: "#92400e",
          }}
        >
          <strong>Historical Note:</strong> This investigation was run on repository <em>{report.repository_id}</em>. Select that repository from the dropdown to see active graph evidence, or click <strong>Investigate</strong> to analyze <em>{selectedRepoId}</em>.
        </div>
      )}

      {/* ── Investigation Summary Card ── */}
      {report && report.status === "COMPLETED" && (!report.repository_id || report.repository_id === selectedRepoId) && (
        <div
          style={{
            backgroundColor: "var(--bg-card)",
            borderRadius: "10px",
            border: "1px solid var(--border-subtle)",
            boxShadow: "var(--shadow-md)",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header Row */}
          <div
            style={{
              padding: "0.85rem 1.25rem",
              backgroundColor: "var(--bg-secondary)",
              borderBottom: "1px solid var(--border-subtle)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-primary)" }}>
                  Investigation Findings: {report.target_module_name || "Repository Scope"}
                </span>
                {report.verification && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      padding: "0.15rem 0.55rem",
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
                    <ShieldCheck size={13} />
                    {report.verification.status}
                  </span>
                )}
                {report.investigation_mode && (
                  <span
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 600,
                      padding: "0.15rem 0.45rem",
                      borderRadius: "4px",
                      backgroundColor: "var(--accent-blue-subtle)",
                      color: "var(--accent-blue)",
                      border: "1px solid var(--border-focus)",
                      textTransform: "uppercase",
                    }}
                  >
                    {report.investigation_mode.replace("_", " ")}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: "0.25rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <span>Repo: <strong>{report.repository_id || selectedRepoId}</strong></span>
                <span>Graph: <strong>{report.graph_name || activeRepo?.graph_name}</strong></span>
                <span>Revision: <strong style={{ fontFamily: "var(--font-mono)" }}>{report.commit_sha?.slice(0, 8) || activeRepo?.commit_sha?.slice(0, 8) || "HEAD"}</strong></span>
                {report.working_tree_fingerprint && (
                  <span>Fingerprint: <strong style={{ fontFamily: "var(--font-mono)" }}>{report.working_tree_fingerprint.slice(0, 8)}</strong></span>
                )}
              </div>
            </div>

            {/* Quick Switch Buttons */}
            <div style={{ display: "flex", gap: "0.4rem" }}>
              <button
                onClick={() => setActiveTab("graph")}
                style={{
                  padding: "0.35rem 0.65rem",
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  borderRadius: "5px",
                  border: "1px solid var(--border-subtle)",
                  backgroundColor: activeTab === "graph" ? "var(--accent-blue-subtle)" : "var(--bg-primary)",
                  color: activeTab === "graph" ? "var(--accent-blue)" : "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Graph View
              </button>
              {report.security_triage_result && (
                <button
                  onClick={() => setActiveTab("security")}
                  style={{
                    padding: "0.35rem 0.65rem",
                    fontSize: "0.74rem",
                    fontWeight: 600,
                    borderRadius: "5px",
                    border: "1px solid var(--border-subtle)",
                    backgroundColor: activeTab === "security" ? "#fee2e2" : "var(--bg-primary)",
                    color: activeTab === "security" ? "#b91c1c" : "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  OSV Advisories ({report.security_triage_result.total_vulnerabilities_count})
                </button>
              )}
              {report.fraud_result && (
                <button
                  onClick={() => setActiveTab("fraud")}
                  style={{
                    padding: "0.35rem 0.65rem",
                    fontSize: "0.74rem",
                    fontWeight: 600,
                    borderRadius: "5px",
                    border: "1px solid var(--border-subtle)",
                    backgroundColor: activeTab === "fraud" ? "#fef3c7" : "var(--bg-primary)",
                    color: activeTab === "fraud" ? "#b45309" : "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  Fraud Cycles
                </button>
              )}
              <button
                onClick={() => setActiveTab("action")}
                style={{
                  padding: "0.35rem 0.65rem",
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  borderRadius: "5px",
                  border: "1px solid var(--border-subtle)",
                  backgroundColor: activeTab === "action" ? "var(--accent-blue-subtle)" : "var(--bg-primary)",
                  color: activeTab === "action" ? "var(--accent-blue)" : "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Verified Action
              </button>
            </div>
          </div>

          {/* Key Findings Metrics Grid */}
          <div
            style={{
              padding: "1rem 1.25rem",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "1rem",
              borderBottom: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-card)",
            }}
          >
            {/* Metric 1: Dependent Callers */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Dependent Callers
              </span>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--accent-blue)" }}>
                {report.impact_result?.total_impacted_count ?? 0}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                Up to {report.impact_result?.max_depth ?? 0} hops traversal
              </span>
            </div>

            {/* Metric 2: Blast Radius */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Topological Blast Radius
              </span>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: sim && sim.baseline_paths_count > 0 ? (sim.blast_radius_score > 0.3 ? "#ef4444" : "#10b981") : "var(--text-secondary)" }}>
                {sim && sim.baseline_paths_count > 0 ? (sim.blast_radius_score * 100).toFixed(0) + "%" : "N/A"}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                {sim?.baseline_paths_count ?? 0} baseline dependency paths
              </span>
            </div>

            {/* Metric 3: Lead Contributors */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Lead Contributors
              </span>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)" }}>
                {report.reviewer_result?.candidates?.length ?? 0}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                {report.reviewer_result?.candidates?.[0]?.name || "No authors recorded"}
              </span>
            </div>

            {/* Metric 4: MCP Tool Sequence */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                MCP Execution Budget
              </span>
              <span style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)" }}>
                {report.budget_used} / {report.budget_used + report.budget_remaining}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                {report.steps.length} deterministic tools planned
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Workspace Navigation Tabs ── */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-subtle)",
          gap: "0.25rem",
          overflowX: "auto",
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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <Layers size={14} />
          Graph Explorer
        </button>

        <button
          onClick={() => setActiveTab("code")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "code" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "code" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <FileCode size={14} />
          Code Inspector
        </button>

        {(investigationMode === "security_triage" || report?.security_triage_result) && (
          <button
            onClick={() => setActiveTab("security")}
            style={{
              padding: "0.55rem 1rem",
              fontSize: "0.82rem",
              fontWeight: 600,
              border: "none",
              borderBottom: activeTab === "security" ? "2px solid #ef4444" : "2px solid transparent",
              backgroundColor: "transparent",
              color: activeTab === "security" ? "#ef4444" : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <ShieldAlert size={14} />
            Security Triage (OSV)
          </button>
        )}

        {(investigationMode === "fraud_demo" || report?.fraud_result) && (
          <button
            onClick={() => setActiveTab("fraud")}
            style={{
              padding: "0.55rem 1rem",
              fontSize: "0.82rem",
              fontWeight: 600,
              border: "none",
              borderBottom: activeTab === "fraud" ? "2px solid #d97706" : "2px solid transparent",
              backgroundColor: "transparent",
              color: activeTab === "fraud" ? "#d97706" : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <DollarSign size={14} />
            Fraud Topology Demo
          </button>
        )}

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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <GitFork size={14} />
          Scenario Simulation
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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <Users size={14} />
          Reviewers & Authors
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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <GitBranch size={14} />
          Agent MCP Trace
        </button>

        <button
          onClick={() => setActiveTab("neighborhood")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "neighborhood" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "neighborhood" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <Network size={14} />
          Neighborhood & Paths
        </button>

        <button
          onClick={() => setActiveTab("provenance")}
          style={{
            padding: "0.55rem 1rem",
            fontSize: "0.82rem",
            fontWeight: 600,
            border: "none",
            borderBottom: activeTab === "provenance" ? "2px solid var(--accent-blue)" : "2px solid transparent",
            backgroundColor: "transparent",
            color: activeTab === "provenance" ? "var(--accent-blue)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <Compass size={14} />
          Source Provenance
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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <FileText size={14} />
          Verified Action
        </button>
      </div>

      {/* ── Tab Panels (Lossless: GraphCanvas stays mounted) ── */}
      <div style={{ display: activeTab === "graph" ? "block" : "none" }}>
        <GraphCanvas
          data={subgraph}
          targetNodeId={selectedModule}
          disappearedNodeIds={disappearedNodeIds}
          disappearedEdgeIds={disappearedEdgeIds}
          survivingNodeIds={survivingNodeIds}
          highlightPathNodes={activePathNodes}
          isLoading={isLoading}
          onSelectTarget={(nodeId) => {
            setSelectedModule(nodeId);
            loadGraph(nodeId, selectedRepoId);
          }}
          onOpenSourceFile={() => {
            setActiveTab("code");
          }}
        />

      </div>

      {activeTab === "code" && (
        <CodeInspector
          repoId={selectedRepoId}
          commitSha={snapshot?.commit_sha}
          activeTargetNodeId={selectedModule}
          onNavigateToGraph={(moduleId) => {
            setSelectedModule(moduleId);
            loadGraph(moduleId, selectedRepoId);
            setActiveTab("graph");
          }}
          onTriggerInvestigation={(q, targetId) => {
            setQuestion(q);
            if (targetId) setSelectedModule(targetId);
            handleInvestigate(targetId);
            setActiveTab("graph");
          }}

        />
      )}


      {activeTab === "security" && (
        <div style={{ backgroundColor: "var(--bg-card)", borderRadius: "8px", border: "1px solid var(--border-subtle)", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ef4444", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <ShieldAlert size={18} />
                Security Vulnerability Triage (OSV.dev Grounded)
              </h3>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", margin: "0.25rem 0 0 0" }}>
                Scanned declared dependency manifests in <strong>{selectedRepoId}</strong> against public OSV advisories.
              </p>
            </div>
            {report?.security_triage_result && (
              <span
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 700,
                  padding: "0.2rem 0.6rem",
                  borderRadius: "20px",
                  backgroundColor: report.security_triage_result.total_vulnerabilities_count === 0 ? "#dcfce7" : "#fee2e2",
                  color: report.security_triage_result.total_vulnerabilities_count === 0 ? "#15803d" : "#b91c1c",
                }}
              >
                {report.security_triage_result.total_vulnerabilities_count} Advisories Found ({report.security_triage_result.dependencies_analyzed_count} Dependencies Analyzed)
              </span>
            )}
          </div>

          {report?.security_triage_result?.remediation_proposal && (
            <div style={{ padding: "0.85rem", borderRadius: "6px", backgroundColor: "#f8fafc", border: "1px solid var(--border-subtle)", marginBottom: "1rem", fontSize: "0.82rem" }}>
              <strong style={{ color: "var(--text-primary)" }}>Remediation Plan:</strong>
              <p style={{ margin: "0.3rem 0 0 0", color: "var(--text-secondary)" }}>
                {report.security_triage_result.remediation_proposal}
              </p>
            </div>
          )}

          {report?.security_triage_result?.vulnerabilities_found && report.security_triage_result.vulnerabilities_found.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {report.security_triage_result.vulnerabilities_found.map((vuln, idx) => (
                <div key={idx} style={{ padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-subtle)", backgroundColor: "var(--bg-primary)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <strong style={{ fontSize: "0.86rem", color: "var(--text-primary)" }}>{vuln.vuln_id}</strong>
                      <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: vuln.severity === "CRITICAL" ? "#fee2e2" : "#fef3c7", color: vuln.severity === "CRITICAL" ? "#b91c1c" : "#b45309" }}>
                        {vuln.severity}
                      </span>
                      <span style={{ fontSize: "0.74rem", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                        {vuln.package_name}@{vuln.package_version}
                      </span>
                    </div>
                    {vuln.reachability_status && (
                      <span style={{ fontSize: "0.72rem", padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: vuln.reachability_status === "REACHABLE_FROM_CODE" ? "#fee2e2" : "#f1f5f9", color: vuln.reachability_status === "REACHABLE_FROM_CODE" ? "#b91c1c" : "#475569", fontWeight: 600 }}>
                        {vuln.reachability_status}
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", margin: "0.4rem 0" }}>{vuln.summary}</p>
                  {vuln.fixed_version && (
                    <div style={{ fontSize: "0.74rem", color: "#15803d", fontWeight: 600 }}>
                      Recommended Fix: Upgrade to <code>{vuln.fixed_version}</code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-secondary)" }}>
              <CheckCircle2 size={32} color="#10b981" style={{ marginBottom: "0.5rem" }} />
              <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.95rem" }}>
                No Known Public Vulnerabilities Detected
              </div>
              <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                All scanned dependencies in this repository snapshot match current non-vulnerable OSV records.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === "fraud" && (
        <div style={{ backgroundColor: "var(--bg-card)", borderRadius: "8px", border: "1px solid var(--border-subtle)", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#d97706", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <DollarSign size={18} />
                Synthetic Financial Graph Fraud Topology (nexusact_fraud_demo)
              </h3>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", margin: "0.25rem 0 0 0" }}>
                Multi-hop circular transfer cycles, shared device hardware fingerprints, and verified benign controls in FalkorDB.
              </p>
            </div>
            {report?.fraud_result && (
              <span
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 700,
                  padding: "0.2rem 0.6rem",
                  borderRadius: "20px",
                  backgroundColor: "#fee2e2",
                  color: "#b91c1c",
                }}
              >
                Risk: {report.fraud_result.risk_indicator}
              </span>
            )}
          </div>

          {/* Synthetic Disclaimer Banner */}
          <div style={{ padding: "0.75rem", borderRadius: "6px", backgroundColor: "#fffbeb", border: "1px solid #fde68a", color: "#92400e", fontSize: "0.78rem", marginBottom: "1rem" }}>
            <strong>Synthetic Demonstration Notice:</strong> This workflow operates exclusively on deterministic synthetic records in FalkorDB graph <code>nexusact_fraud_demo</code>. No real individuals, accounts, or banks are represented.
          </div>

          {report?.fraud_result?.patterns_detected && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "1.5rem" }}>
              <h4 style={{ fontSize: "0.86rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                Detected Suspicious Topology Patterns ({report.fraud_result.patterns_detected.length})
              </h4>
              {report.fraud_result.patterns_detected.map((pat, idx) => (
                <div key={idx} style={{ padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-subtle)", backgroundColor: "var(--bg-primary)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <strong style={{ fontSize: "0.86rem", color: "var(--text-primary)" }}>{pat.pattern_type}</strong>
                      <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: (pat.risk_score ?? 0.5) >= 0.75 ? "#fee2e2" : "#fef3c7", color: (pat.risk_score ?? 0.5) >= 0.75 ? "#b91c1c" : "#b45309" }}>
                        Risk: {pat.risk_score !== undefined ? `${(pat.risk_score * 100).toFixed(0)}%` : pat.severity}
                      </span>
                    </div>
                    {pat.amount_involved && (
                      <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-primary)" }}>
                        Flow: ${pat.amount_involved.toLocaleString()}
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", margin: "0.4rem 0" }}>{pat.details}</p>
                  {pat.participating_nodes && pat.participating_nodes.length > 0 && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.4rem" }}>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Path:</span>
                      {pat.participating_nodes.map((node: string, i: number) => (
                        <span key={i} style={{ padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: "var(--bg-card)", border: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                          {node}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Benign Control Verification */}
          {report?.fraud_result?.benign_controls && (
            <div>
              <h4 style={{ fontSize: "0.86rem", fontWeight: 700, margin: "0 0 0.5rem 0", color: "#15803d" }}>
                Verified Benign Control Accounts (False-Positive Suppression)
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                {report.fraud_result.benign_controls.map((ctrl, idx) => (
                  <div key={idx} style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid #86efac", backgroundColor: "#f0fdf4" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ fontSize: "0.82rem", color: "#15803d", fontFamily: "var(--font-mono)" }}>{ctrl.account_id}</strong>
                      <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "#15803d" }}>VERIFIED BENIGN</span>
                    </div>
                    <p style={{ fontSize: "0.74rem", color: "#166534", margin: "0.3rem 0 0 0" }}>{ctrl.status_reason || ctrl.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === "simulation" && (
        <CounterfactualDiff
          simulation={report?.simulation_result ?? null}
          activeView={simulationView}
          onToggleView={setSimulationView}
        />
      )}

      {activeTab === "reviewers" && (
        <ReviewerRankings data={report?.reviewer_result ?? null} />
      )}

      {activeTab === "trace" && (
        <AgentTrace
          steps={report?.steps ?? []}
          investigationId={report?.investigation_id}
        />
      )}

      {activeTab === "neighborhood" && (
        <div style={{ backgroundColor: "var(--bg-card)", borderRadius: "8px", border: "1px solid var(--border-subtle)", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                Neighborhood & Directed Paths
              </h3>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", margin: "0.25rem 0 0 0" }}>
                Topological path verification and 1-hop caller/callee connections in FalkorDB graph.
              </p>
            </div>
            {activePathNodes.length >= 2 && (
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  backgroundColor: "var(--accent-blue-subtle)",
                  color: "var(--accent-blue)",
                  padding: "0.2rem 0.55rem",
                  borderRadius: "4px",
                  border: "1px solid var(--border-focus)",
                }}
              >
                {activePathNodes.length - 1 === 1
                  ? "Direct Relationship (1-hop path)"
                  : `Multi-Hop Path (${activePathNodes.length - 1} hops)`}
              </span>
            )}
          </div>

          {/* 1. Verified Path Result */}
          {(activePathNodes.length >= 2 || report?.shortest_path_result) && (
            <div style={{ marginBottom: "1.5rem", padding: "0.75rem", backgroundColor: "var(--bg-muted)", borderRadius: "6px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.5rem" }}>
                <Compass size={14} color="var(--accent-blue)" />
                <strong style={{ fontSize: "0.8rem", color: "var(--text-primary)" }}>
                  Verified Graph Path Chain:
                </strong>
              </div>
              {report?.shortest_path_result?.explanation && (
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "0.6rem" }}>
                  {report.shortest_path_result.explanation}
                </p>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                {(report?.shortest_path_result?.path_nodes || activePathNodes).map((node, i, arr) => (
                  <React.Fragment key={node}>
                    <button
                      onClick={() => setSelectedModule(node.replace(/^mod:/, ""))}
                      style={{
                        padding: "0.25rem 0.55rem",
                        borderRadius: "4px",
                        backgroundColor: i === 0 ? "var(--bg-card)" : i === arr.length - 1 ? "var(--accent-blue-subtle)" : "var(--bg-card)",
                        border: i === 0 || i === arr.length - 1 ? "1px solid var(--accent-blue)" : "1px solid var(--border-subtle)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.76rem",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        cursor: "pointer",
                      }}
                      title={i === 0 ? "Path Source" : i === arr.length - 1 ? "Path Target" : `Intermediate Node (Hop ${i})`}
                    >
                      {node.replace(/^mod:/, "")}
                      {i === 0 && <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginLeft: "0.3rem" }}>(source)</span>}
                      {i === arr.length - 1 && <span style={{ fontSize: "0.68rem", color: "var(--accent-blue)", marginLeft: "0.3rem" }}>(target)</span>}
                      {i > 0 && i < arr.length - 1 && <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginLeft: "0.3rem" }}>(hop {i})</span>}
                    </button>
                    {i < arr.length - 1 && (
                      <span style={{ color: "var(--accent-blue)", fontWeight: 700, fontSize: "0.8rem", display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
                        <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          DEPENDS_ON
                        </span>
                        →
                      </span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* 2. 1-Hop Neighborhood Connections */}
          {(() => {
            const targetIdClean = (selectedModule || report?.target_module_name || "").trim().replace(/^mod:/, "");
            const hasExplicitNeighborhood = Boolean(report?.neighborhood_result);

            const incoming = hasExplicitNeighborhood
              ? report!.neighborhood_result!.incoming_dependents.map((n) => ({
                  id: n.id,
                  name: n.name,
                  detail: n.source_file || "",
                }))
              : (subgraph?.edges || [])
                  .filter((e) => {
                    const tgt = e.target.replace(/^mod:/, "");
                    return tgt === targetIdClean;
                  })
                  .map((e) => ({
                    id: e.source,
                    name: e.source.replace(/^mod:/, ""),
                    detail: e.label || "DEPENDS_ON",
                  }));

            const outgoing = hasExplicitNeighborhood
              ? report!.neighborhood_result!.outgoing_dependencies.map((n) => ({
                  id: n.id,
                  name: n.name,
                  detail: "",
                }))
              : (subgraph?.edges || [])
                  .filter((e) => {
                    const src = e.source.replace(/^mod:/, "");
                    return src === targetIdClean;
                  })
                  .map((e) => ({
                    id: e.target,
                    name: e.target.replace(/^mod:/, ""),
                    detail: e.label || "DEPENDS_ON",
                  }));

            const hasAnyConnections = incoming.length > 0 || outgoing.length > 0;

            if (!hasAnyConnections && activePathNodes.length < 2 && !report?.shortest_path_result) {
              return (
                <div style={{ textAlign: "center", padding: "1.5rem", color: "var(--text-muted)" }}>
                  <p style={{ fontSize: "0.82rem", margin: 0 }}>
                    No path or neighborhood connections were found for '{selectedModule || "target"}' in the active graph.
                  </p>
                  <p style={{ fontSize: "0.75rem", marginTop: "0.3rem" }}>
                    Run an investigation or select a module connected to other components in the repository.
                  </p>
                </div>
              );
            }

            return (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "0.75rem", backgroundColor: "var(--bg-card)" }}>
                  <h4 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--accent-blue)", marginBottom: "0.5rem" }}>
                    Incoming Dependents / Callers ({incoming.length})
                  </h4>
                  <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.78rem" }}>
                    {incoming.map((n) => (
                      <li key={n.id} style={{ padding: "0.3rem 0", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <button
                          onClick={() => setSelectedModule(n.name)}
                          style={{
                            background: "none",
                            border: "none",
                            color: "var(--text-primary)",
                            fontWeight: 600,
                            fontFamily: "var(--font-mono)",
                            cursor: "pointer",
                            padding: 0,
                            textAlign: "left",
                          }}
                        >
                          {n.name}
                        </button>
                        {n.detail && <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", fontFamily: "var(--font-mono)" }}>{n.detail}</span>}
                      </li>
                    ))}
                    {incoming.length === 0 && (
                      <li style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No incoming dependent callers.</li>
                    )}
                  </ul>
                </div>

                <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "0.75rem", backgroundColor: "var(--bg-card)" }}>
                  <h4 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--accent-blue)", marginBottom: "0.5rem" }}>
                    Outgoing Dependencies / Callees ({outgoing.length})
                  </h4>
                  <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.78rem" }}>
                    {outgoing.map((n) => (
                      <li key={n.id} style={{ padding: "0.3rem 0", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <button
                          onClick={() => setSelectedModule(n.name)}
                          style={{
                            background: "none",
                            border: "none",
                            color: "var(--text-primary)",
                            fontWeight: 600,
                            fontFamily: "var(--font-mono)",
                            cursor: "pointer",
                            padding: 0,
                            textAlign: "left",
                          }}
                        >
                          {n.name}
                        </button>
                        {n.detail && <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", fontFamily: "var(--font-mono)" }}>{n.detail}</span>}
                      </li>
                    ))}
                    {outgoing.length === 0 && (
                      <li style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No outgoing dependency modules.</li>
                    )}
                  </ul>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {activeTab === "provenance" && (
        <div style={{ backgroundColor: "var(--bg-card)", borderRadius: "8px", border: "1px solid var(--border-subtle)", padding: "1.25rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.5rem", color: "var(--text-primary)" }}>
            Data Source Capabilities & Provenance
          </h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Discloses exact collection sources, revisions, and limitations for the selected repository.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {sourceMetadata?.sources?.map((s) => (
              <div key={s.source_id} style={{ border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "0.85rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>
                    {s.source_type === "github" ? "GitHub Public API" : "Local Git Repository"}
                  </span>
                  <span style={{ fontSize: "0.72rem", padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: "#dcfce7", color: "#15803d", fontWeight: 600 }}>
                    {s.status}
                  </span>
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "0.4rem" }}>
                  <div>Categories: {s.data_categories.join(", ")}</div>
                  <div>Retrieved at: {s.retrieval_timestamp}</div>
                </div>
              </div>
            ))}

            {activeRepo?.known_gaps && activeRepo.known_gaps.length > 0 && (
              <div style={{ border: "1px solid #fde68a", backgroundColor: "#fffbeb", borderRadius: "6px", padding: "0.85rem" }}>
                <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "#92400e", marginBottom: "0.4rem" }}>
                  Disclosed Evidence Gaps:
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.78rem", color: "#78350f" }}>
                  {activeRepo.known_gaps.map((gap, i) => (
                    <li key={i}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
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
