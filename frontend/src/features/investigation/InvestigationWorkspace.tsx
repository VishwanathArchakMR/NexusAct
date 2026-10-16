import React, { useState, useEffect } from "react";
import type {
  InvestigationReport,
  ModuleSuggestion,
  SubgraphResponse,
  IngestionReport,
  RepositoryRecord,
  SourceMetadataOutput,
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
  FolderGit2,
  Globe,
  AlertTriangle,
  HelpCircle,
  Plus,
  Network,
  Compass,
} from "lucide-react";

export interface InvestigationWorkspaceProps {
  selectedRepoId?: string;
  onSelectRepoId?: (id: string) => void;
}

export const InvestigationWorkspace: React.FC<InvestigationWorkspaceProps> = ({
  selectedRepoId: propRepoId,
  onSelectRepoId,
}) => {
  // Repositories state
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>(propRepoId || "repo:local_nexusact");
  const [sourceMetadata, setSourceMetadata] = useState<SourceMetadataOutput | null>(null);

  const [prevPropRepoId, setPrevPropRepoId] = useState(propRepoId);
  if (propRepoId && propRepoId !== prevPropRepoId) {
    setPrevPropRepoId(propRepoId);
    setSelectedRepoId(propRepoId);
  }

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
    "What might be affected if I modify the graph client, and who has relevant experience?"
  );

  const [activeTab, setActiveTab] = useState<
    "graph" | "trace" | "reviewers" | "simulation" | "neighborhood" | "provenance" | "action"
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
          loadRepoMetadata(selectedRepoId),
          loadModules(undefined, selectedRepoId),
          loadGraph(undefined, selectedRepoId),
        ]);
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepoId, loadRepoMetadata, loadModules, loadGraph]);

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
      await loadRepoMetadata(selectedRepoId);
      await loadModules(undefined, selectedRepoId);
      await loadGraph(undefined, selectedRepoId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setIsRefreshing(false);
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
        5
      );
      setReport(rep);
      if (rep.target_module_id) {
        setSelectedModule(rep.target_module_id);
        await loadGraph(rep.target_module_id, selectedRepoId);
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
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "1.5rem 1rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* Repository Scope & Onboarding Banner */}
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
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Refresh repository to latest commit"
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
            {isRefreshing ? "Refreshing..." : "Refresh Revision"}
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
            Onboard Repository
          </button>
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
              <li key={`warn-${idx}`}>Parser warning: {warn}</li>
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
            backgroundColor: "rgba(0,0,0,0.5)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1rem",
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: "12px",
              padding: "1.5rem",
              width: "100%",
              maxWidth: "520px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                Onboard Engineering Repository
              </h3>
              <button
                onClick={() => setShowOnboardModal(false)}
                style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleOnboardSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.4rem" }}>
                  Source Method
                </label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setOnboardType("github")}
                    style={{
                      flex: 1,
                      padding: "0.5rem",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      borderRadius: "6px",
                      border: "1px solid",
                      borderColor: onboardType === "github" ? "var(--accent-blue)" : "var(--border-subtle)",
                      backgroundColor: onboardType === "github" ? "#eff6ff" : "#ffffff",
                      color: onboardType === "github" ? "var(--accent-blue)" : "var(--text-secondary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <Globe size={14} />
                    Public GitHub URL
                  </button>
                  <button
                    type="button"
                    onClick={() => setOnboardType("local")}
                    style={{
                      flex: 1,
                      padding: "0.5rem",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      borderRadius: "6px",
                      border: "1px solid",
                      borderColor: onboardType === "local" ? "var(--accent-blue)" : "var(--border-subtle)",
                      backgroundColor: onboardType === "local" ? "#eff6ff" : "#ffffff",
                      color: onboardType === "local" ? "var(--accent-blue)" : "var(--text-secondary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <FolderGit2 size={14} />
                    Local Git Path
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

      {/* Investigation Controls Card */}
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
            Dynamic Graph Intelligence Investigation
          </h2>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
            Submit an engineering question in natural language. NexusAct resolves targets, discovers available evidence, and plans MCP tool execution dynamically.
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
              Natural-Language Engineering Question
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

          {/* Optional Target Module Selector */}
          <div>
            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>
              Target Module (Optional)
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
            Ambiguous Target Detected — Please Clarify
          </div>
          <p style={{ fontSize: "0.82rem", color: "#78350f", margin: "0.4rem 0 0.8rem 0" }}>
            {report.summary}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {report.ambiguity_candidates?.map((c) => (
              <button
                key={c.module_id}
                onClick={() => {
                  setSelectedModule(c.module_id);
                  handleInvestigate(c.module_id);
                }}
                style={{
                  padding: "0.4rem 0.75rem",
                  fontSize: "0.78rem",
                  borderRadius: "6px",
                  border: "1px solid #d97706",
                  backgroundColor: "var(--bg-card)",
                  color: "#d97706",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                }}
              >
                <span>{c.module_name}</span>
                <span style={{ fontSize: "0.7rem", opacity: 0.7 }}>({c.match_type})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Unresolved Limitation Banner */}
      {report?.status === "UNRESOLVED" && (
        <div
          style={{
            backgroundColor: "#fffbeb",
            borderRadius: "8px",
            border: "1px solid #fde68a",
            padding: "1rem 1.25rem",
            color: "#92400e",
            fontSize: "0.82rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 700, color: "#92400e", marginBottom: "0.3rem" }}>
            <AlertTriangle size={16} color="#d97706" />
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

      {/* First-Class Investigation Summary Card (Scoped strictly to current repository) */}
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
                {report.is_heuristic_fallback && (
                  <span
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 600,
                      padding: "0.15rem 0.45rem",
                      borderRadius: "4px",
                      backgroundColor: "var(--bg-muted)",
                      color: "var(--text-secondary)",
                      border: "1px solid var(--border-subtle)",
                    }}
                    title="Adaptive MCP tool sequence executed (deterministic tool planning)"
                  >
                    MCP Adaptive Plan
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: "0.25rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <span>Repo: <strong>{report.repository_id || selectedRepoId}</strong></span>
                <span>Graph: <strong>{report.graph_name || activeRepo?.graph_name}</strong></span>
                <span>Revision: <strong style={{ fontFamily: "var(--font-mono)" }}>{report.commit_sha?.slice(0, 8) || activeRepo?.commit_sha?.slice(0, 8) || "HEAD"}</strong></span>
                <span>Question: <em>"{report.question}"</em></span>
              </div>
            </div>

            {/* Quick Tab Switch Buttons */}
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
                Graph Canvas
              </button>
              <button
                onClick={() => setActiveTab("action")}
                style={{
                  padding: "0.35rem 0.75rem",
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: "var(--accent-blue)",
                  color: "#ffffff",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                }}
              >
                Verified Action →
              </button>
            </div>
          </div>

          {/* Metrics Strip */}
          <div
            style={{
              padding: "0.6rem 1.25rem",
              backgroundColor: "var(--bg-primary)",
              borderBottom: "1px solid var(--border-subtle)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: "0.75rem",
              fontSize: "0.78rem",
            }}
          >
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>TOOLS EXECUTED</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)" }}>{report.budget_used}</strong>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>UPSTREAM CALLERS</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--accent-blue)" }}>{report.impact_result?.total_impacted_count ?? 0}</strong>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>DISRUPTED PATHS</span>
              <strong style={{ fontSize: "0.95rem", color: "#ef4444" }}>{report.simulation_result?.disappeared_paths_count ?? 0}</strong>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>SURVIVING PATHS</span>
              <strong style={{ fontSize: "0.95rem", color: "#10b981" }}>{report.simulation_result?.surviving_paths_count ?? 0}</strong>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>BLAST RADIUS</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)" }}>
                {report.simulation_result ? `${(report.simulation_result.blast_radius_score * 100).toFixed(1)}%` : "0.0%"}
              </strong>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>LEAD REVIEWER</span>
              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>
                {report.reviewer_result?.candidates[0]?.name || "None designated"}
              </strong>
            </div>
          </div>

          {/* Summary & Findings Section */}
          <div style={{ padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            <p style={{ fontSize: "0.85rem", color: "var(--text-primary)", lineHeight: 1.55 }}>
              {report.summary}
            </p>

            {/* Approach: Tool Decision Trace Pills */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.2rem" }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)" }}>Tool Approach:</span>
              {report.steps.map((st) => (
                <span
                  key={st.step_number}
                  style={{
                    fontSize: "0.7rem",
                    padding: "0.15rem 0.45rem",
                    borderRadius: "4px",
                    backgroundColor: "var(--bg-secondary)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-secondary)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  #{st.step_number} {st.tool_name.replace(/^nexusact_/, "")}
                </span>
              ))}
            </div>

            {/* Verified Multi-Hop Path Highlight if available */}
            {activePathNodes.length >= 2 && (
              <div
                style={{
                  marginTop: "0.4rem",
                  padding: "0.5rem 0.75rem",
                  backgroundColor: "var(--accent-blue-subtle)",
                  borderRadius: "6px",
                  border: "1px solid var(--border-focus)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  fontSize: "0.76rem",
                  flexWrap: "wrap",
                }}
              >
                <strong style={{ color: "var(--accent-blue)" }}>
                  {activePathNodes.length - 1 === 1
                    ? "Direct Relationship (1-hop path):"
                    : `Multi-Hop Graph Path (${activePathNodes.length - 1} hops):`}
                </strong>
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", flexWrap: "wrap" }}>
                  {activePathNodes.map((pNode, idx) => (
                    <React.Fragment key={pNode}>
                      <span
                        style={{
                          backgroundColor: "var(--bg-card)",
                          border: "1px solid var(--border-subtle)",
                          borderRadius: "4px",
                          padding: "0.15rem 0.4rem",
                          fontWeight: 600,
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.72rem",
                        }}
                      >
                        {pNode.replace(/^mod:/, "")}
                      </span>
                      {idx < activePathNodes.length - 1 && <span>→</span>}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            {/* Disclaimer on Structural vs Runtime Evidence */}
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "0.2rem" }}>
              * Evidence derived from static AST dependency topology, commit history, and counterfactual simulation in FalkorDB. Structural impact predicts call boundaries; runtime testing validates functional behavior.
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-subtle)",
          gap: "0.5rem",
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
          Dependency Graph
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
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          <GitFork size={14} />
          Counterfactual Diff
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
          Reviewer Evidence {report?.reviewer_result ? `(${report.reviewer_result.candidates.length})` : ""}
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
          Agent MCP Trace {report ? `(${report.steps.length})` : ""}
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

      {/* Tab Panels */}
      {activeTab === "graph" && (
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
        />
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

          {/* 1. Verified Path Result (from active investigation, findings, or shortest path) */}
          {(activePathNodes.length >= 2 || report?.shortest_path_result) && (
            <div
              style={{
                marginBottom: "1.25rem",
                padding: "0.85rem 1rem",
                backgroundColor: "var(--bg-muted)",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
              }}
            >
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
