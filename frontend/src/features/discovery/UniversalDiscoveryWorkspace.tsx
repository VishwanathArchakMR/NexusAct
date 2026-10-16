import React, { useState, useEffect } from "react";
import {
  Globe,
  Database,
  Search,
  AlertTriangle,
  ExternalLink,
  Check,
  History,
  RotateCcw,
  Sparkles,
  FolderGit2,
  Network,
  ArrowRight,
} from "lucide-react";
import {
  fetchPublicSources,
  askUniversalGaf,
  fetchPublicSubgraph,
  fetchSavedInvestigations,
  confirmInvestigationAction,
  fetchRepositories,
} from "../../api/client";
import type {
  SourceConnectorInfo,
  UniversalInvestigationResult,
  PublicSubgraphResponse,
  SavedInvestigation,
} from "../../types/discovery";
import type { RepositoryRecord } from "../../types/investigation";

export type InputMode = "public" | "repository" | "combined";
export type SourceScope = "all" | "ai_ecosystem" | "research";

export interface UniversalDiscoveryWorkspaceProps {
  selectedRepoId?: string;
  onSelectRepoId?: (id: string) => void;
}

export const UniversalDiscoveryWorkspace: React.FC<UniversalDiscoveryWorkspaceProps> = ({
  selectedRepoId: propRepoId,
  onSelectRepoId,
}) => {
  // Input mode & repository selection
  const [inputMode, setInputMode] = useState<InputMode>("public");
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>(propRepoId || "repo:local_nexusact");
  const [scope, setScope] = useState<SourceScope>("all");
  const [selectedProviders, setSelectedProviders] = useState<Record<string, boolean>>({
    huggingface: true,
    openalex: true,
    crossref: true,
    wikidata: true,
  });

  // Query & execution state
  const [question, setQuestion] = useState("");
  const [sources, setSources] = useState<Record<string, SourceConnectorInfo>>({});
  const [investigating, setInvestigating] = useState(false);
  const [investigationResult, setInvestigationResult] = useState<UniversalInvestigationResult | null>(null);

  // Graph state: scoped investigation vs persistent corpus
  const [displayMode, setDisplayMode] = useState<"investigation" | "corpus" | "empty">("empty");
  const [corpusGraph, setCorpusGraph] = useState<PublicSubgraphResponse | null>(null);
  const [savedInvestigations, setSavedInvestigations] = useState<SavedInvestigation[]>([]);
  const [selectedNode, setSelectedNode] = useState<{
    id: string;
    label: string;
    type: string;
    properties?: Record<string, unknown>;
  } | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{
    source: string;
    target: string;
    type: string;
    confidence?: string;
    evidence?: string;
    provenance?: string;
  } | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);
  const [actionConfirmed, setActionConfirmed] = useState(false);
  const [confirmingAction, setConfirmingAction] = useState(false);

  const [prevPropRepoId, setPrevPropRepoId] = useState(propRepoId);
  if (propRepoId && propRepoId !== prevPropRepoId) {
    setPrevPropRepoId(propRepoId);
    setSelectedRepoId(propRepoId);
  }

  // Load sources, repositories, and history on mount
  useEffect(() => {
    loadSources();
    loadRepos();
    loadSavedHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadSources() {
    try {
      const res = await fetchPublicSources();
      setSources(res.sources);
    } catch (err: unknown) {
      console.warn("Failed loading public sources:", err);
    }
  }

  async function loadRepos() {
    try {
      const repos = await fetchRepositories();
      setRepositories(repos);
      if (repos.length > 0 && !repos.some((r) => r.id === selectedRepoId)) {
        const defaultRepo = repos[0].id;
        setSelectedRepoId(defaultRepo);
        onSelectRepoId?.(defaultRepo);
      }
    } catch (err: unknown) {
      console.warn("Failed loading repositories in Universal GAF:", err);
    }
  }

  async function loadCorpusGraph() {
    try {
      const g = await fetchPublicSubgraph(100);
      setCorpusGraph(g);
      setDisplayMode("corpus");
    } catch (err: unknown) {
      console.warn("Public subgraph load failed:", err);
    }
  }

  async function loadSavedHistory() {
    try {
      const res = await fetchSavedInvestigations(10);
      setSavedInvestigations(res.investigations);
    } catch (err: unknown) {
      console.warn("Failed loading investigation history:", err);
    }
  }

  const activeRepo = repositories.find((r) => r.id === selectedRepoId);

  // Suggested queries by mode
  const suggestedQueriesByMode: Record<InputMode, string[]> = {
    public: [
      "Explore citation relationships between neural network research works.",
      "Which institutions are associated with researchers behind transformer papers?",
      "Which datasets are documented as used to train open-source models?",
      "Find Hugging Face models created by major AI research laboratories.",
    ],
    repository: [
      "Which modules depend on the database layer?",
      "Show module dependencies and blast radius for routing components.",
      "What are the core imported dependencies and modules in this repository?",
      "Who knows about authentication and graph client modules?",
    ],
    combined: [
      "How do repository model utilities connect to Hugging Face models?",
      "Are external dependencies in this project referenced in public papers or Wikidata?",
      "Trace research publications and model architectures relevant to this codebase.",
    ],
  };

  async function handleSearch(queryToRun?: string) {
    const q = queryToRun || question;
    if (!q.trim()) return;

    try {
      setInvestigating(true);
      setError(null);
      setActionConfirmed(false);
      setSelectedNode(null);
      setSelectedEdge(null);

      // Determine explicit source list
      let selectedSources: string[] | undefined = undefined;
      if (inputMode === "public" || inputMode === "combined") {
        selectedSources = Object.entries(selectedProviders)
          .filter(([, enabled]) => enabled)
          .map(([id]) => id);
      }

      const options = {
        inputMode,
        repositoryId: inputMode !== "public" ? (activeRepo?.id || selectedRepoId) : null,
        graphName: inputMode !== "public" ? activeRepo?.graph_name : null,
        commitSha: inputMode !== "public" ? activeRepo?.commit_sha : null,
      };

      const res = await askUniversalGaf(q, selectedSources, 5, options);
      setInvestigationResult(res);
      setDisplayMode("investigation");
      await loadSavedHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Investigation failed";
      setError(msg);
    } finally {
      setInvestigating(false);
    }
  }

  async function handleConfirmAction(actionId: string) {
    try {
      setConfirmingAction(true);
      await confirmInvestigationAction(actionId);
      setActionConfirmed(true);
      if (investigationResult?.next_action) {
        investigationResult.next_action.status = "CONFIRMED";
      }
      await loadSavedHistory();
    } catch (err: unknown) {
      console.error("Action confirmation failed:", err);
    } finally {
      setConfirmingAction(false);
    }
  }

  function handleSelectSaved(saved: SavedInvestigation) {
    setQuestion(saved.question);
    if (saved.input_mode && (saved.input_mode === "public" || saved.input_mode === "repository" || saved.input_mode === "combined")) {
      setInputMode(saved.input_mode as InputMode);
    }
    if (saved.repository_id) {
      setSelectedRepoId(saved.repository_id);
      onSelectRepoId?.(saved.repository_id);
    }
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  // Node styling helper
  const getNodeColor = (type: string) => {
    switch (type.toUpperCase()) {
      case "MODULE":
        return { bg: "#eef2ff", border: "#6366f1", text: "#4338ca", dot: "#6366f1" };
      case "REPOSITORY":
        return { bg: "#f0fdfa", border: "#14b8a6", text: "#0f766e", dot: "#14b8a6" };
      case "MODEL":
        return { bg: "#f5f3ff", border: "#8b5cf6", text: "#6d28d9", dot: "#8b5cf6" };
      case "DATASET":
        return { bg: "#ecfdf5", border: "#10b981", text: "#047857", dot: "#10b981" };
      case "PAPER":
        return { bg: "#eff6ff", border: "#3b82f6", text: "#1d4ed8", dot: "#3b82f6" };
      case "PERSON":
        return { bg: "#fffbeb", border: "#f59e0b", text: "#b45309", dot: "#f59e0b" };
      case "ORGANIZATION":
        return { bg: "#ecfeff", border: "#06b6d4", text: "#0e7490", dot: "#06b6d4" };
      case "TOPIC":
        return { bg: "#f8fafc", border: "#64748b", text: "#334155", dot: "#64748b" };
      default:
        return { bg: "#f1f5f9", border: "#94a3b8", text: "#475569", dot: "#94a3b8" };
    }
  };

  // Determine which graph to display: investigation-scoped vs corpus
  const activeGraphData: PublicSubgraphResponse =
    displayMode === "investigation" && investigationResult?.scoped_subgraph
      ? investigationResult.scoped_subgraph
      : displayMode === "corpus" && corpusGraph
      ? corpusGraph
      : { nodes: [], edges: [], total_nodes: 0, total_edges: 0 };

  const rawNodes = activeGraphData.nodes || [];
  const dedupNodesMap = new Map<string, (typeof rawNodes)[0]>();
  for (const n of rawNodes) {
    if (!dedupNodesMap.has(n.id)) {
      dedupNodesMap.set(n.id, n);
    }
  }
  const allNodes = Array.from(dedupNodesMap.values());
  const filteredNodes =
    selectedTypeFilter === "ALL"
      ? allNodes
      : allNodes.filter((n) => n.type.toUpperCase() === selectedTypeFilter);

  const rawEdges = activeGraphData.edges || [];
  const dedupEdgesMap = new Map<string, (typeof rawEdges)[0]>();
  for (const e of rawEdges) {
    const key = `${e.source}-${e.type}-${e.target}`;
    if (!dedupEdgesMap.has(key)) {
      dedupEdgesMap.set(key, e);
    }
  }
  const allEdges = Array.from(dedupEdgesMap.values());

  return (
    <div style={{ padding: "1.5rem 2rem", maxWidth: "1400px", margin: "0 auto" }}>
      {/* Title & Description */}
      <div style={{ marginBottom: "1.25rem" }}>
        <h1
          style={{
            fontSize: "1.6rem",
            fontWeight: 700,
            color: "#1e293b",
            margin: 0,
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
          }}
        >
          <Globe color="#2563eb" size={26} />
          Universal GraphAction Fabric (Universal GAF)
        </h1>
        <p style={{ color: "#64748b", margin: "0.25rem 0 0 0", fontSize: "0.9rem" }}>
          Input-driven multi-domain investigation workspace. Select an explicit input mode to investigate live public knowledge, isolated repository codebases, or cross-domain evidence.
        </p>
      </div>

      {/* STEP 3: EXPLICIT INVESTIGATION INPUT SELECTOR */}
      <div
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #cbd5e1",
          borderRadius: "10px",
          padding: "1.1rem 1.25rem",
          boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
          marginBottom: "1.25rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Investigation Input Mode:
            </span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
            Current target: <strong style={{ color: "#0f172a" }}>{inputMode === "public" ? "Approved Public Knowledge Providers" : inputMode === "repository" ? (activeRepo?.name || selectedRepoId) : `${activeRepo?.name || selectedRepoId} + Public Knowledge`}</strong>
          </div>
        </div>

        {/* Mode Selector Tabs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "0.6rem", marginBottom: "1rem" }}>
          {/* Mode A: Public Knowledge Discovery */}
          <button
            onClick={() => {
              setInputMode("public");
              setError(null);
            }}
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              border: "1px solid",
              borderColor: inputMode === "public" ? "#2563eb" : "#e2e8f0",
              backgroundColor: inputMode === "public" ? "#eff6ff" : "#f8fafc",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.85rem", color: inputMode === "public" ? "#1d4ed8" : "#334155" }}>
              <Globe size={16} /> Mode A — Public Knowledge Discovery
            </div>
            <div style={{ fontSize: "0.74rem", color: "#64748b", marginTop: "0.2rem" }}>
              Query Hugging Face, OpenAlex, Crossref, and Wikidata for real metadata and persistent relationships.
            </div>
          </button>

          {/* Mode B: Selected Repository */}
          <button
            onClick={() => {
              setInputMode("repository");
              setError(null);
            }}
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              border: "1px solid",
              borderColor: inputMode === "repository" ? "#2563eb" : "#e2e8f0",
              backgroundColor: inputMode === "repository" ? "#eff6ff" : "#f8fafc",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.85rem", color: inputMode === "repository" ? "#1d4ed8" : "#334155" }}>
              <FolderGit2 size={16} /> Mode B — Selected Repository
            </div>
            <div style={{ fontSize: "0.74rem", color: "#64748b", marginTop: "0.2rem" }}>
              Investigate the actual code graph, module dependencies, and blast radius of an onboarded repository.
            </div>
          </button>

          {/* Mode C: Combined Repository + Public Evidence */}
          <button
            onClick={() => {
              setInputMode("combined");
              setError(null);
            }}
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              border: "1px solid",
              borderColor: inputMode === "combined" ? "#2563eb" : "#e2e8f0",
              backgroundColor: inputMode === "combined" ? "#eff6ff" : "#f8fafc",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.85rem", color: inputMode === "combined" ? "#1d4ed8" : "#334155" }}>
              <Network size={16} /> Mode C — Repository + Public Evidence
            </div>
            <div style={{ fontSize: "0.74rem", color: "#64748b", marginTop: "0.2rem" }}>
              Dual-source investigation: analyze code modules alongside external models and citation evidence.
            </div>
          </button>
        </div>

        {/* Mode-Specific Contextual Controls */}
        {inputMode === "public" && (
          <div style={{ padding: "0.6rem 0.8rem", backgroundColor: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0", marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.8rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#475569" }}>Public Providers:</span>
                {["huggingface", "openalex", "crossref", "wikidata"].map((srcId) => {
                  const conn = sources[srcId];
                  const checked = selectedProviders[srcId] ?? true;
                  return (
                    <label key={`chk-${srcId}`} style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.75rem", color: "#334155", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) =>
                          setSelectedProviders((prev) => ({ ...prev, [srcId]: e.target.checked }))
                        }
                      />
                      <span>{conn?.display_name || srcId}</span>
                    </label>
                  );
                })}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Scope Quick Filter:</span>
                <button
                  type="button"
                  onClick={() => {
                    setScope("all");
                    setSelectedProviders({ huggingface: true, openalex: true, crossref: true, wikidata: true });
                  }}
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.15rem 0.45rem",
                    borderRadius: "4px",
                    border: "1px solid #cbd5e1",
                    backgroundColor: scope === "all" ? "#eff6ff" : "#ffffff",
                    color: scope === "all" ? "#2563eb" : "#475569",
                    cursor: "pointer",
                  }}
                >
                  All
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setScope("ai_ecosystem");
                    setSelectedProviders({ huggingface: true, openalex: false, crossref: false, wikidata: true });
                  }}
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.15rem 0.45rem",
                    borderRadius: "4px",
                    border: "1px solid #cbd5e1",
                    backgroundColor: scope === "ai_ecosystem" ? "#eff6ff" : "#ffffff",
                    color: scope === "ai_ecosystem" ? "#2563eb" : "#475569",
                    cursor: "pointer",
                  }}
                >
                  Models
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setScope("research");
                    setSelectedProviders({ huggingface: false, openalex: true, crossref: true, wikidata: false });
                  }}
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.15rem 0.45rem",
                    borderRadius: "4px",
                    border: "1px solid #cbd5e1",
                    backgroundColor: scope === "research" ? "#eff6ff" : "#ffffff",
                    color: scope === "research" ? "#2563eb" : "#475569",
                    cursor: "pointer",
                  }}
                >
                  Papers
                </button>
              </div>
            </div>
          </div>
        )}

        {(inputMode === "repository" || inputMode === "combined") && (
          <div style={{ padding: "0.75rem 0.9rem", backgroundColor: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0", marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.4rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "#1e293b" }}>Selected Repository:</span>
                <select
                  value={selectedRepoId}
                  onChange={(e) => {
                    const newId = e.target.value;
                    setSelectedRepoId(newId);
                    onSelectRepoId?.(newId);
                    setInvestigationResult(null);
                    setError(null);
                  }}
                  style={{
                    padding: "0.35rem 0.75rem",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    backgroundColor: "#ffffff",
                    color: "#0f172a",
                    cursor: "pointer",
                  }}
                >
                  {repositories.map((r) => (
                    <option key={`repo-opt-${r.id}`} value={r.id}>
                      {r.name} ({r.source_type === "github" ? "GitHub" : "Local"} • {r.commit_sha.slice(0, 7)})
                    </option>
                  ))}
                </select>
              </div>

              {activeRepo && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.74rem", color: "#475569" }}>
                  <span style={{ padding: "0.15rem 0.45rem", borderRadius: "4px", backgroundColor: "#e2e8f0", fontFamily: "monospace" }}>
                    Graph: {activeRepo.graph_name}
                  </span>
                  <span>Revision: <strong>{activeRepo.commit_sha.slice(0, 8)}</strong></span>
                  <span>Modules: <strong>{activeRepo.module_count}</strong></span>
                  <span>Edges: <strong>{activeRepo.edge_count}</strong></span>
                </div>
              )}
            </div>

            {/* Empty module disclosure */}
            {activeRepo && activeRepo.module_count === 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem", color: "#b45309", backgroundColor: "#fffbeb", padding: "0.35rem 0.6rem", borderRadius: "4px", border: "1px solid #fef3c7", marginTop: "0.4rem" }}>
                <AlertTriangle size={13} color="#d97706" />
                <span>
                  <strong>Data Disclosure:</strong> Selected repository '{activeRepo.name}' contains 0 parsed modules and 0 dependency edges in graph '{activeRepo.graph_name}'. Investigations will report these real ingestion gaps honestly.
                </span>
              </div>
            )}

            {/* In Combined Mode, also show provider selection */}
            {inputMode === "combined" && (
              <div style={{ marginTop: "0.5rem", paddingTop: "0.5rem", borderTop: "1px dashed #e2e8f0", display: "flex", alignItems: "center", gap: "0.8rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#475569" }}>Complementary Public Sources:</span>
                {["huggingface", "openalex", "crossref", "wikidata"].map((srcId) => (
                  <label key={`chk-comb-${srcId}`} style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.75rem", color: "#334155", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={selectedProviders[srcId] ?? true}
                      onChange={(e) =>
                        setSelectedProviders((prev) => ({ ...prev, [srcId]: e.target.checked }))
                      }
                    />
                    <span>{sources[srcId]?.display_name || srcId}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Input Question Box & Action Button */}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder={
              inputMode === "public"
                ? "Ask Universal GAF: e.g. Explore citation relationships between neural network research works..."
                : inputMode === "repository"
                ? `Ask Codebase: e.g. Which modules depend on the database layer in ${activeRepo?.name || 'this repo'}?`
                : `Ask Combined: e.g. How do repository model utilities connect to Hugging Face models?`
            }
            style={{
              flex: 1,
              padding: "0.7rem 1rem",
              borderRadius: "6px",
              border: "1px solid #94a3b8",
              fontSize: "0.92rem",
              outline: "none",
            }}
          />
          <button
            onClick={() => handleSearch()}
            disabled={investigating}
            style={{
              backgroundColor: investigating ? "#94a3b8" : "#2563eb",
              color: "#ffffff",
              padding: "0.7rem 1.4rem",
              borderRadius: "6px",
              border: "none",
              fontWeight: 600,
              fontSize: "0.88rem",
              cursor: investigating ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              transition: "background-color 0.15s ease",
            }}
          >
            <Search size={16} />
            {investigating ? "Investigating..." : "Investigate"}
          </button>
        </div>

        {/* Suggested Queries for Active Mode */}
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "0.73rem", color: "#64748b", fontWeight: 600 }}>Suggested investigations:</span>
          {suggestedQueriesByMode[inputMode].map((sq, idx) => (
            <button
              key={`sq-${inputMode}-${idx}`}
              onClick={() => {
                setQuestion(sq);
                handleSearch(sq);
              }}
              style={{
                fontSize: "0.73rem",
                color: "#2563eb",
                backgroundColor: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "14px",
                padding: "0.2rem 0.6rem",
                cursor: "pointer",
              }}
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            padding: "0.85rem 1rem",
            color: "#991b1b",
            fontSize: "0.85rem",
            marginBottom: "1.25rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* ACTIVE REQUEST & INVESTIGATION CONTEXT BADGE (Step 3 & Step 6) */}
      {investigationResult && (
        <div
          style={{
            backgroundColor: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: "8px",
            padding: "0.75rem 1rem",
            marginBottom: "1.25rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "0.5rem",
            fontSize: "0.78rem",
            color: "#166534",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
            <span style={{ fontWeight: 700, textTransform: "uppercase", backgroundColor: "#dcfce7", padding: "0.15rem 0.5rem", borderRadius: "4px" }}>
              Active Context: {investigationResult.input_mode?.toUpperCase() || inputMode.toUpperCase()}
            </span>
            <span>ID: <code style={{ fontFamily: "monospace" }}>{investigationResult.investigation_id}</code></span>
            {investigationResult.repository_id && (
              <span>Repo: <strong>{investigationResult.repository_id}</strong> (Graph: {investigationResult.graph_name || "isolated"}, SHA: {investigationResult.commit_sha?.slice(0, 8) || "head"})</span>
            )}
            {investigationResult.plan.selected_source_ids?.length > 0 && (
              <span>Connectors: <strong>{investigationResult.plan.selected_source_ids.join(", ")}</strong></span>
            )}
          </div>
          <div>
            <span>Execution: <strong>{(investigationResult.execution_time_ms / 1000).toFixed(2)}s</strong></span>
          </div>
        </div>
      )}

      {/* STEP 6: USEFUL AND EXPLAINABLE INVESTIGATION RESULTS */}
      {investigationResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", marginBottom: "1.5rem" }}>
          {/* Main Result & Structured Explanation */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #cbd5e1",
              borderRadius: "10px",
              padding: "1.25rem 1.5rem",
              boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
              <div>
                <span
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "#2563eb",
                    backgroundColor: "#eff6ff",
                    padding: "0.2rem 0.5rem",
                    borderRadius: "4px",
                  }}
                >
                  Investigation Explanation
                </span>
                <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#0f172a", margin: "0.5rem 0 0 0" }}>
                  {investigationResult.question}
                </h2>
              </div>
              <div style={{ fontSize: "0.8rem", color: "#64748b", display: "flex", gap: "1rem" }}>
                <span>Ingested: <strong>{investigationResult.records_ingested}</strong></span>
                <span>Relationships: <strong>{investigationResult.relationships.length}</strong></span>
                <span>Entities: <strong>{investigationResult.entities.length}</strong></span>
              </div>
            </div>

            {/* 1. What Input was Investigated? */}
            <div style={{ marginBottom: "0.85rem", backgroundColor: "#f8fafc", padding: "0.6rem 0.8rem", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: "0.2rem" }}>
                1. Input & Target Scope
              </div>
              <div style={{ fontSize: "0.84rem", color: "#1e293b" }}>
                {investigationResult.input_mode === "repository" ? (
                  <span>
                    Investigated codebase repository <strong>{investigationResult.repository_id}</strong> in FalkorDB graph <code>{investigationResult.graph_name}</code> (Revision: {investigationResult.commit_sha?.slice(0, 8)}).
                  </span>
                ) : investigationResult.input_mode === "combined" ? (
                  <span>
                    Combined investigation across codebase <strong>{investigationResult.repository_id}</strong> and approved public providers (<code>{investigationResult.plan.selected_source_ids.join(", ")}</code>).
                  </span>
                ) : (
                  <span>
                    Investigated approved public knowledge sources (<code>{investigationResult.plan.selected_source_ids.join(", ")}</code>) in FalkorDB graph <code>nexusact_public</code>.
                  </span>
                )}
              </div>
            </div>

            {/* 2. How did the Agent investigate it? */}
            <div style={{ marginBottom: "0.85rem" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                2. Investigation Approach
              </div>
              <p style={{ fontSize: "0.88rem", color: "#334155", margin: 0, lineHeight: 1.5 }}>
                {investigationResult.approach || investigationResult.summary}
              </p>
            </div>

            {/* 3. What was Discovered? */}
            <div style={{ marginBottom: "0.85rem" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                3. Evidence-Backed Findings
              </div>
              {investigationResult.findings.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.85rem", color: "#1e293b", lineHeight: 1.6 }}>
                  {investigationResult.findings.map((f, idx) => (
                    <li key={`finding-${idx}`}>{f}</li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#64748b", fontStyle: "italic" }}>
                  No verified relationships could be proven between the returned records with current metadata.
                </p>
              )}
            </div>

            {/* 4. What Remains Unknown? */}
            {investigationResult.coverage_limitations.length > 0 && (
              <div style={{ marginBottom: "0.85rem", backgroundColor: "#fffbeb", border: "1px solid #fef3c7", borderRadius: "6px", padding: "0.75rem 1rem" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#92400e", display: "flex", alignItems: "center", gap: "0.3rem", marginBottom: "0.2rem" }}>
                  <AlertTriangle size={13} /> 4. Coverage Disclosures & Unknowns
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.8rem", color: "#78350f", lineHeight: 1.5 }}>
                  {investigationResult.coverage_limitations.map((lim, idx) => (
                    <li key={`lim-${idx}`}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 5. What should happen next? */}
            {investigationResult.next_action && (
              <div
                style={{
                  border: "1px solid #bfdbfe",
                  backgroundColor: "#f0f9ff",
                  borderRadius: "8px",
                  padding: "0.85rem 1rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#0369a1", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <Sparkles size={13} /> 5. Grounded Next Action
                  </div>
                  <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0c4a6e", marginTop: "0.2rem" }}>
                    {investigationResult.next_action.title}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#0369a1", marginTop: "0.1rem" }}>
                    {investigationResult.next_action.description}
                  </div>
                </div>

                <div>
                  {actionConfirmed || investigationResult.next_action.status === "CONFIRMED" ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.3rem",
                        backgroundColor: "#dcfce7",
                        color: "#15803d",
                        fontWeight: 600,
                        fontSize: "0.8rem",
                        padding: "0.4rem 0.85rem",
                        borderRadius: "6px",
                      }}
                    >
                      <Check size={14} /> Action Confirmed in Graph
                    </span>
                  ) : (
                    <button
                      onClick={() => handleConfirmAction(investigationResult.next_action!.id)}
                      disabled={confirmingAction}
                      style={{
                        backgroundColor: "#0284c7",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        padding: "0.45rem 1rem",
                        fontSize: "0.82rem",
                        fontWeight: 600,
                        cursor: confirmingAction ? "default" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                      }}
                    >
                      {confirmingAction ? "Confirming..." : "Confirm Action in Graph"}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Evidence-Backed Relationships Table */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              padding: "1.1rem 1.25rem",
              boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
            }}
          >
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#1e293b", margin: "0 0 0.85rem 0" }}>
              Evidence-Backed Relationships ({investigationResult.relationships.length})
            </h3>
            {investigationResult.relationships.length === 0 ? (
              <div style={{ color: "#64748b", fontSize: "0.85rem", fontStyle: "italic" }}>
                No direct typed relationships could be proven between the returned records with current metadata.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left", color: "#475569" }}>
                      <th style={{ padding: "0.55rem" }}>Source Entity</th>
                      <th style={{ padding: "0.55rem" }}>Relationship</th>
                      <th style={{ padding: "0.55rem" }}>Target Entity</th>
                      <th style={{ padding: "0.55rem" }}>Confidence</th>
                      <th style={{ padding: "0.55rem" }}>Evidence</th>
                      <th style={{ padding: "0.55rem" }}>Provenance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {investigationResult.relationships.map((rel, idx) => (
                      <tr
                        key={`rel-row-${idx}-${rel.source}-${rel.target}`}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          cursor: "pointer",
                          backgroundColor:
                            selectedEdge?.source === rel.source && selectedEdge?.target === rel.target
                              ? "#eff6ff"
                              : "transparent",
                        }}
                        onClick={() =>
                          setSelectedEdge({
                            source: rel.source,
                            target: rel.target,
                            type: rel.type,
                            confidence: rel.confidence,
                            evidence: rel.evidence,
                            provenance: rel.provenance_url,
                          })
                        }
                      >
                        <td style={{ padding: "0.55rem", fontWeight: 600, color: "#0f172a" }}>{rel.source}</td>
                        <td style={{ padding: "0.55rem" }}>
                          <span
                            style={{
                              backgroundColor: "#f1f5f9",
                              color: "#334155",
                              padding: "0.15rem 0.45rem",
                              borderRadius: "4px",
                              fontFamily: "monospace",
                              fontWeight: 600,
                              fontSize: "0.72rem",
                            }}
                          >
                            {rel.type}
                          </span>
                        </td>
                        <td style={{ padding: "0.55rem", fontWeight: 600, color: "#0f172a" }}>{rel.target}</td>
                        <td style={{ padding: "0.55rem" }}>
                          <span
                            style={{
                              color: rel.confidence === "EXACT" ? "#16a34a" : "#2563eb",
                              backgroundColor: rel.confidence === "EXACT" ? "#f0fdf4" : "#eff6ff",
                              padding: "0.12rem 0.4rem",
                              borderRadius: "8px",
                              fontSize: "0.68rem",
                              fontWeight: 700,
                            }}
                          >
                            {rel.confidence}
                          </span>
                        </td>
                        <td style={{ padding: "0.55rem", color: "#64748b" }}>{rel.evidence}</td>
                        <td style={{ padding: "0.55rem" }}>
                          {rel.provenance_url ? (
                            <a
                              href={rel.provenance_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                color: "#2563eb",
                                textDecoration: "none",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.2rem",
                              }}
                            >
                              Source Record <ExternalLink size={11} />
                            </a>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 4 & STEP 7: INPUT-SCOPED GRAPH VISUALIZATION */}
      <div
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "1.25rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#1e293b", margin: 0, display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Database size={16} color={displayMode === "investigation" ? "#2563eb" : "#7c3aed"} />
              {displayMode === "investigation"
                ? `Investigation Graph (${activeGraphData.total_nodes} nodes, ${activeGraphData.total_edges} edges)`
                : displayMode === "corpus"
                ? `Persistent Public Corpus (${activeGraphData.total_nodes} nodes, ${activeGraphData.total_edges} edges)`
                : "Graph Evidence Visualizer"}
            </h3>
            <div style={{ fontSize: "0.74rem", color: "#64748b", marginTop: "0.15rem" }}>
              {displayMode === "investigation"
                ? `Scoped to current investigation: "${investigationResult?.question}"`
                : displayMode === "corpus"
                ? "Showing global persistent corpus (nexusact_public)"
                : "No active graph displayed. Submit an investigation or browse persistent knowledge corpus."}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            {displayMode === "investigation" && (
              <button
                onClick={loadCorpusGraph}
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  padding: "0.3rem 0.65rem",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  backgroundColor: "#ffffff",
                  color: "#475569",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                }}
              >
                <Database size={12} /> Browse Persistent Corpus
              </button>
            )}

            {displayMode === "corpus" && investigationResult && (
              <button
                onClick={() => setDisplayMode("investigation")}
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  padding: "0.3rem 0.65rem",
                  borderRadius: "6px",
                  border: "1px solid #93c5fd",
                  backgroundColor: "#eff6ff",
                  color: "#1d4ed8",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                }}
              >
                <ArrowRight size={12} /> Return to Investigation Graph
              </button>
            )}
          </div>
        </div>

        {/* Legend and Node Type Filters */}
        {displayMode !== "empty" && (
          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center", marginBottom: "0.85rem" }}>
            <span style={{ fontSize: "0.73rem", color: "#64748b", fontWeight: 600 }}>Filter:</span>
            {["ALL", "MODULE", "PAPER", "MODEL", "PERSON", "ORGANIZATION", "DATASET", "TOPIC"].map((t) => (
              <button
                key={`filter-${t}`}
                onClick={() => setSelectedTypeFilter(t)}
                style={{
                  fontSize: "0.7rem",
                  fontWeight: 600,
                  padding: "0.18rem 0.5rem",
                  borderRadius: "12px",
                  border: "1px solid",
                  borderColor: selectedTypeFilter === t ? "#2563eb" : "#e2e8f0",
                  backgroundColor: selectedTypeFilter === t ? "#eff6ff" : "#ffffff",
                  color: selectedTypeFilter === t ? "#2563eb" : "#475569",
                  cursor: "pointer",
                }}
              >
                {t}
              </button>
            ))}
            <button
              onClick={() => {
                setSelectedNode(null);
                setSelectedEdge(null);
                setSelectedTypeFilter("ALL");
              }}
              style={{
                fontSize: "0.7rem",
                fontWeight: 600,
                padding: "0.18rem 0.5rem",
                borderRadius: "12px",
                border: "1px solid #cbd5e1",
                backgroundColor: "#f8fafc",
                color: "#475569",
                cursor: "pointer",
                marginLeft: "auto",
                display: "flex",
                alignItems: "center",
                gap: "0.25rem",
              }}
            >
              <RotateCcw size={11} /> Reset Filter
            </button>
          </div>
        )}

        {/* Graph Canvas Grid & Detail Inspector */}
        {displayMode === "empty" ? (
          <div
            style={{
              padding: "2.5rem 1.5rem",
              textAlign: "center",
              backgroundColor: "#f8fafc",
              borderRadius: "6px",
              border: "1px dashed #cbd5e1",
            }}
          >
            <Database size={32} color="#94a3b8" style={{ margin: "0 auto 0.5rem auto" }} />
            <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#334155" }}>
              No investigation graph currently loaded
            </div>
            <p style={{ fontSize: "0.82rem", color: "#64748b", maxWidth: "520px", margin: "0.4rem auto 1rem auto" }}>
              Universal GAF generates scoped, evidence-backed graphs for each specific input. Enter an investigation above or browse previously saved corpus records.
            </p>
            <button
              onClick={loadCorpusGraph}
              style={{
                padding: "0.5rem 1rem",
                fontSize: "0.8rem",
                fontWeight: 600,
                backgroundColor: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                color: "#2563eb",
                cursor: "pointer",
              }}
            >
              Browse Persistent Public Knowledge Graph (nexusact_public)
            </button>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: selectedNode || selectedEdge ? "2fr 1fr" : "1fr", gap: "1rem" }}>
            {/* Node Grid Visualization */}
            <div
              style={{
                minHeight: "220px",
                maxHeight: "360px",
                overflowY: "auto",
                border: "1px solid #e2e8f0",
                borderRadius: "6px",
                padding: "0.75rem",
                backgroundColor: "#f8fafc",
              }}
            >
              {filteredNodes.length > 0 ? (
                <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                  {filteredNodes.map((n) => {
                    const style = getNodeColor(n.type);
                    const isSelected = selectedNode?.id === n.id;
                    return (
                      <button
                        key={`graph-node-${n.id}`}
                        onClick={() => {
                          setSelectedNode(n);
                          setSelectedEdge(null);
                        }}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.35rem",
                          padding: "0.35rem 0.65rem",
                          borderRadius: "16px",
                          border: isSelected ? "2px solid #2563eb" : `1px solid ${style.border}`,
                          backgroundColor: style.bg,
                          color: style.text,
                          fontSize: "0.74rem",
                          fontWeight: 600,
                          cursor: "pointer",
                          boxShadow: isSelected ? "0 0 0 2px rgba(37,99,235,0.2)" : "none",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <span
                          style={{
                            width: "7px",
                            height: "7px",
                            borderRadius: "50%",
                            backgroundColor: style.dot,
                          }}
                        />
                        <span>{n.label}</span>
                        <span style={{ fontSize: "0.65rem", opacity: 0.75 }}>({n.type})</span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div style={{ color: "#94a3b8", fontSize: "0.85rem", fontStyle: "italic", textAlign: "center", padding: "2rem" }}>
                  No entities match filter '{selectedTypeFilter}'.
                </div>
              )}
            </div>

            {/* Inspector Panel for Selected Node or Edge */}
            {(selectedNode || selectedEdge) && (
              <div
                style={{
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  padding: "1rem",
                  backgroundColor: "#ffffff",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
                }}
              >
                {selectedNode && (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          color: getNodeColor(selectedNode.type).text,
                          backgroundColor: getNodeColor(selectedNode.type).bg,
                          border: `1px solid ${getNodeColor(selectedNode.type).border}`,
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                        }}
                      >
                        {selectedNode.type.toUpperCase()}
                      </span>
                      <button
                        onClick={() => setSelectedNode(null)}
                        style={{ border: "none", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem" }}
                      >
                        ✕
                      </button>
                    </div>
                    <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "0.92rem", color: "#0f172a", wordBreak: "break-word" }}>
                      {selectedNode.label}
                    </h4>
                    <div style={{ fontSize: "0.74rem", color: "#64748b", marginBottom: "0.6rem", wordBreak: "break-all" }}>
                      <strong>Canonical ID:</strong> {selectedNode.id}
                    </div>

                    {/* Connected edges for this node */}
                    <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "0.5rem" }}>
                      <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#475569", marginBottom: "0.3rem" }}>
                        Connected Relationships:
                      </div>
                      {allEdges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length > 0 ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                          {allEdges
                            .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                            .slice(0, 6)
                            .map((e, idx) => (
                              <div
                                key={`conn-edge-${idx}-${e.source}-${e.type}-${e.target}`}
                                style={{
                                  fontSize: "0.72rem",
                                  padding: "0.25rem 0.4rem",
                                  backgroundColor: "#f8fafc",
                                  borderRadius: "4px",
                                  border: "1px solid #e2e8f0",
                                }}
                              >
                                <span style={{ fontWeight: 600 }}>{e.source === selectedNode.id ? "Outgoing" : "Incoming"}:</span>{" "}
                                <code>{e.type}</code> → {e.source === selectedNode.id ? e.target : e.source}
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: "0.72rem", color: "#94a3b8", fontStyle: "italic" }}>
                          No direct connected edges in this subgraph slice.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedEdge && (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          color: "#2563eb",
                          backgroundColor: "#eff6ff",
                          border: "1px solid #bfdbfe",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                        }}
                      >
                        RELATIONSHIP EVIDENCE
                      </span>
                      <button
                        onClick={() => setSelectedEdge(null)}
                        style={{ border: "none", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem" }}
                      >
                        ✕
                      </button>
                    </div>
                    <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "0.92rem", color: "#0f172a" }}>
                      {selectedEdge.type}
                    </h4>
                    <div style={{ fontSize: "0.74rem", color: "#475569", lineHeight: 1.5 }}>
                      <div><strong>From:</strong> {selectedEdge.source}</div>
                      <div><strong>To:</strong> {selectedEdge.target}</div>
                      <div><strong>Confidence:</strong> {selectedEdge.confidence || "VERIFIED"}</div>
                      {selectedEdge.evidence && <div><strong>Evidence:</strong> {selectedEdge.evidence}</div>}
                      {selectedEdge.provenance && (
                        <div style={{ marginTop: "0.4rem" }}>
                          <a
                            href={selectedEdge.provenance}
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: "#2563eb", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.2rem" }}
                          >
                            Provenance Link <ExternalLink size={11} />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Saved Investigations & Memory */}
      <div
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "1.25rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#1e293b", margin: 0, display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <History size={16} color="#2563eb" /> Graph-Backed Investigation Memory ({savedInvestigations.length})
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
            Persisted in FalkorDB (PublicInvestigation nodes)
          </span>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.82rem", margin: "0 0 1rem 0" }}>
          Past investigations, evidence chains, and user-confirmed follow-up actions remain preserved in FalkorDB across sessions. Click any investigation to reload its context.
        </p>

        {savedInvestigations.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "0.75rem" }}>
            {savedInvestigations.map((inv) => (
              <div
                key={`saved-${inv.investigation_id}`}
                onClick={() => handleSelectSaved(inv)}
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: "6px",
                  padding: "0.85rem",
                  backgroundColor: "#f8fafc",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.4rem" }}>
                  <div style={{ fontWeight: 600, fontSize: "0.84rem", color: "#0f172a" }}>
                    {inv.question}
                  </div>
                  {inv.action_status === "CONFIRMED" && (
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "#15803d", backgroundColor: "#dcfce7", padding: "0.1rem 0.35rem", borderRadius: "4px" }}>
                      CONFIRMED
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.3rem" }}>
                  {inv.summary}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#2563eb", marginTop: "0.4rem", display: "flex", alignItems: "center", gap: "0.3rem", flexWrap: "wrap" }}>
                  <span style={{ backgroundColor: "#eff6ff", padding: "0.1rem 0.35rem", borderRadius: "3px", fontWeight: 600 }}>
                    Mode: {inv.input_mode || "public"}
                  </span>
                  {inv.repository_id && (
                    <span>Repo: {inv.repository_id}</span>
                  )}
                  {inv.sources && <span>Sources: {inv.sources}</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "#94a3b8", fontSize: "0.85rem", fontStyle: "italic" }}>
            No saved investigations yet. Run an investigation to persist memory into FalkorDB.
          </div>
        )}
      </div>
    </div>
  );
};
