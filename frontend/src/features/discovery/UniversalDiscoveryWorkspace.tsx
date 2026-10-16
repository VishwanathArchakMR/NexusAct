import React, { useState, useEffect } from "react";
import {
  Globe,
  Database,
  Search,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Cpu,
  Check,
  History,
  RotateCcw,
  Sparkles,
  Link as LinkIcon,
  BookOpen,
} from "lucide-react";
import {
  fetchPublicSources,
  askUniversalGaf,
  fetchPublicSubgraph,
  fetchSavedInvestigations,
  confirmInvestigationAction,
} from "../../api/client";
import type {
  SourceConnectorInfo,
  UniversalInvestigationResult,
  PublicSubgraphResponse,
  SavedInvestigation,
} from "../../types/discovery";

export type SourceScope = "all" | "ai_ecosystem" | "research";

export const UniversalDiscoveryWorkspace: React.FC = () => {
  const [scope, setScope] = useState<SourceScope>("all");
  const [question, setQuestion] = useState("");
  const [sources, setSources] = useState<Record<string, SourceConnectorInfo>>({});
  const [loadingSources, setLoadingSources] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [investigationResult, setInvestigationResult] = useState<UniversalInvestigationResult | null>(null);
  const [subgraph, setSubgraph] = useState<PublicSubgraphResponse | null>(null);
  const [savedInvestigations, setSavedInvestigations] = useState<SavedInvestigation[]>([]);
  const [selectedNode, setSelectedNode] = useState<{ id: string; label: string; type: string; properties?: Record<string, unknown> } | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string; type: string; confidence?: string; evidence?: string; provenance?: string } | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);
  const [actionConfirmed, setActionConfirmed] = useState(false);
  const [confirmingAction, setConfirmingAction] = useState(false);

  // Suggested queries by scope
  const suggestedQueries: Record<SourceScope, string[]> = {
    all: [
      "Explore citation relationships between neural network research works.",
      "Which institutions are associated with researchers behind transformer papers?",
      "Which datasets are documented as used to train open-source models?",
      "Find Hugging Face models created by major AI research laboratories.",
    ],
    ai_ecosystem: [
      "Which datasets are documented as used to train open-source models?",
      "Find Hugging Face models created by major AI research laboratories.",
      "Show models and evaluation datasets linked to llama architectures.",
    ],
    research: [
      "Explore citation relationships between neural network research works.",
      "Which institutions are associated with researchers behind transformer papers?",
      "Which papers explicitly reference foundational deep learning publications?",
    ],
  };

  useEffect(() => {
    loadSources();
    loadPublicGraph();
    loadSavedHistory();
  }, []);

  async function loadSources() {
    try {
      setLoadingSources(true);
      const res = await fetchPublicSources();
      setSources(res.sources);
    } catch (err: unknown) {
      console.warn("Failed loading public sources:", err);
    } finally {
      setLoadingSources(false);
    }
  }

  async function loadPublicGraph() {
    try {
      const g = await fetchPublicSubgraph(100);
      setSubgraph(g);
    } catch (err: unknown) {
      console.warn("Public subgraph load:", err);
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

  async function handleSearch(queryToRun?: string) {
    const q = queryToRun || question;
    if (!q.trim()) return;

    try {
      setInvestigating(true);
      setError(null);
      setActionConfirmed(false);
      setSelectedNode(null);
      setSelectedEdge(null);

      let selectedSources: string[] | undefined = undefined;
      if (scope === "ai_ecosystem") {
        selectedSources = ["huggingface", "wikidata"];
      } else if (scope === "research") {
        selectedSources = ["openalex", "crossref"];
      }

      const res = await askUniversalGaf(q, selectedSources, 5);
      setInvestigationResult(res);
      await loadPublicGraph();
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
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  // Node styling helper
  const getNodeColor = (type: string) => {
    switch (type.toUpperCase()) {
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

  // Deduplicated nodes and edges
  const rawNodes = subgraph?.nodes || [];
  const dedupNodesMap = new Map<string, (typeof rawNodes)[0]>();
  for (const n of rawNodes) {
    if (!dedupNodesMap.has(n.id)) {
      dedupNodesMap.set(n.id, n);
    }
  }
  const allNodes = Array.from(dedupNodesMap.values());
  const filteredNodes = selectedTypeFilter === "ALL"
    ? allNodes
    : allNodes.filter((n) => n.type.toUpperCase() === selectedTypeFilter);

  const rawEdges = subgraph?.edges || [];
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
      <div style={{ marginBottom: "1.5rem" }}>
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
          Universal Public-Data Discovery (GAF)
        </h1>
        <p style={{ color: "#64748b", margin: "0.25rem 0 0 0", fontSize: "0.9rem" }}>
          Single unified public-data investigation workspace. Query Hugging Face, OpenAlex, Crossref, and Wikidata in FalkorDB with persistent memory and verified graph evidence.
        </p>
      </div>

      {/* Source Health & Status Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "0.75rem",
          marginBottom: "1.5rem",
        }}
      >
        {loadingSources ? (
          <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Checking public connector status...</div>
        ) : (
          Object.values(sources).map((conn) => {
            const queried = investigationResult?.sources_queried?.[conn.source_id];
            return (
              <div
                key={conn.source_id}
                style={{
                  backgroundColor: "#ffffff",
                  border: queried ? "1px solid #93c5fd" : "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "0.75rem 1rem",
                  boxShadow: queried ? "0 2px 4px rgba(37,99,235,0.06)" : "0 1px 2px rgba(0,0,0,0.03)",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b" }}>{conn.display_name}</div>
                    <div style={{ fontSize: "0.72rem", color: "#64748b", marginTop: "0.1rem" }}>
                      Types: {conn.entity_types.join(", ")}
                    </div>
                  </div>
                  <div>
                    {conn.healthy ? (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.25rem",
                          fontSize: "0.72rem",
                          color: "#16a34a",
                          backgroundColor: "#f0fdf4",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "12px",
                          fontWeight: 600,
                        }}
                      >
                        <CheckCircle2 size={11} /> ONLINE
                      </span>
                    ) : (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.25rem",
                          fontSize: "0.72rem",
                          color: "#dc2626",
                          backgroundColor: "#fef2f2",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "12px",
                          fontWeight: 600,
                        }}
                      >
                        <AlertTriangle size={11} /> DEGRADED
                      </span>
                    )}
                  </div>
                </div>

                {queried && (
                  <div
                    style={{
                      marginTop: "0.4rem",
                      paddingTop: "0.4rem",
                      borderTop: "1px dashed #e2e8f0",
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.72rem",
                    }}
                  >
                    <span style={{ color: "#2563eb", fontWeight: 600 }}>Queried</span>
                    <span style={{ color: "#0f172a", fontWeight: 600 }}>{queried.records_fetched} records fetched</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Unified Query Bar with Contextual Scope Controls */}
      <div
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #cbd5e1",
          borderRadius: "10px",
          padding: "1rem",
          boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
          marginBottom: "1.5rem",
        }}
      >
        {/* Source Scope Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.8rem", color: "#475569", fontWeight: 600 }}>Investigation Scope:</span>
          <button
            onClick={() => setScope("all")}
            style={{
              fontSize: "0.78rem",
              fontWeight: 600,
              padding: "0.3rem 0.75rem",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: scope === "all" ? "#2563eb" : "#cbd5e1",
              backgroundColor: scope === "all" ? "#eff6ff" : "#ffffff",
              color: scope === "all" ? "#2563eb" : "#475569",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.3rem",
            }}
          >
            <Globe size={13} /> All relevant sources
          </button>
          <button
            onClick={() => setScope("ai_ecosystem")}
            style={{
              fontSize: "0.78rem",
              fontWeight: 600,
              padding: "0.3rem 0.75rem",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: scope === "ai_ecosystem" ? "#2563eb" : "#cbd5e1",
              backgroundColor: scope === "ai_ecosystem" ? "#eff6ff" : "#ffffff",
              color: scope === "ai_ecosystem" ? "#2563eb" : "#475569",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.3rem",
            }}
          >
            <Cpu size={13} /> AI models and datasets
          </button>
          <button
            onClick={() => setScope("research")}
            style={{
              fontSize: "0.78rem",
              fontWeight: 600,
              padding: "0.3rem 0.75rem",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: scope === "research" ? "#2563eb" : "#cbd5e1",
              backgroundColor: scope === "research" ? "#eff6ff" : "#ffffff",
              color: scope === "research" ? "#2563eb" : "#475569",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.3rem",
            }}
          >
            <BookOpen size={13} /> Research papers and citations
          </button>
        </div>

        {/* Input & Action */}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder="Ask GAF: e.g. Explore citation relationships between neural network research works..."
            style={{
              flex: 1,
              padding: "0.7rem 1rem",
              borderRadius: "6px",
              border: "1px solid #94a3b8",
              fontSize: "0.95rem",
              outline: "none",
            }}
          />
          <button
            onClick={() => handleSearch()}
            disabled={investigating}
            style={{
              backgroundColor: investigating ? "#94a3b8" : "#2563eb",
              color: "#ffffff",
              padding: "0.7rem 1.5rem",
              borderRadius: "6px",
              border: "none",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: investigating ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <Search size={16} />
            {investigating ? "Investigating..." : "Investigate"}
          </button>
        </div>

        {/* Suggested Queries */}
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>Suggested investigations:</span>
          {suggestedQueries[scope].map((sq, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQuestion(sq);
                handleSearch(sq);
              }}
              style={{
                fontSize: "0.75rem",
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

      {error && (
        <div
          style={{
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            padding: "0.85rem 1rem",
            color: "#991b1b",
            fontSize: "0.85rem",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {/* Investigation Explanation & Grounded Results Card (Phase 5) */}
      {investigationResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", marginBottom: "2rem" }}>
          {/* Explanation Card */}
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
                <span>Time: <strong>{(investigationResult.execution_time_ms / 1000).toFixed(2)}s</strong></span>
              </div>
            </div>

            {/* Approach */}
            <div style={{ marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Investigation Approach
              </div>
              <p style={{ fontSize: "0.88rem", color: "#334155", margin: 0, lineHeight: 1.5 }}>
                {investigationResult.approach || investigationResult.summary}
              </p>
            </div>

            {/* Findings */}
            <div style={{ marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Evidence-Backed Findings
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

            {/* Limitations */}
            {investigationResult.coverage_limitations.length > 0 && (
              <div style={{ marginBottom: "1.25rem", backgroundColor: "#fffbeb", border: "1px solid #fef3c7", borderRadius: "6px", padding: "0.75rem 1rem" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#92400e", display: "flex", alignItems: "center", gap: "0.3rem", marginBottom: "0.2rem" }}>
                  <AlertTriangle size={13} /> Coverage Disclosures & Limitations
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.8rem", color: "#78350f", lineHeight: 1.5 }}>
                  {investigationResult.coverage_limitations.map((lim, idx) => (
                    <li key={`lim-${idx}`}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommended Next Action (Phase 7) */}
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
                    <Sparkles size={13} /> Recommended Graph Action
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
                      <Check size={14} /> Action Confirmed & Saved
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
              padding: "1.25rem",
              boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
            }}
          >
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#1e293b", margin: "0 0 1rem 0" }}>
              Evidence-Backed Public Relationships ({investigationResult.relationships.length})
            </h3>
            {investigationResult.relationships.length === 0 ? (
              <div style={{ color: "#64748b", fontSize: "0.85rem", fontStyle: "italic" }}>
                No direct typed relationships could be proven between the returned records with current metadata.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left", color: "#475569" }}>
                      <th style={{ padding: "0.6rem" }}>Source Entity</th>
                      <th style={{ padding: "0.6rem" }}>Relationship</th>
                      <th style={{ padding: "0.6rem" }}>Target Entity</th>
                      <th style={{ padding: "0.6rem" }}>Confidence</th>
                      <th style={{ padding: "0.6rem" }}>Evidence Field</th>
                      <th style={{ padding: "0.6rem" }}>Provenance URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {investigationResult.relationships.map((rel, idx) => (
                      <tr
                        key={`rel-row-${idx}-${rel.source}-${rel.target}`}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          cursor: "pointer",
                          backgroundColor: selectedEdge?.source === rel.source && selectedEdge?.target === rel.target ? "#eff6ff" : "transparent",
                        }}
                        onClick={() => setSelectedEdge({
                          source: rel.source,
                          target: rel.target,
                          type: rel.type,
                          confidence: rel.confidence,
                          evidence: rel.evidence,
                          provenance: rel.provenance_url,
                        })}
                      >
                        <td style={{ padding: "0.6rem", fontWeight: 600, color: "#0f172a" }}>{rel.source}</td>
                        <td style={{ padding: "0.6rem" }}>
                          <span
                            style={{
                              backgroundColor: "#f1f5f9",
                              color: "#334155",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "4px",
                              fontFamily: "monospace",
                              fontWeight: 600,
                              fontSize: "0.75rem",
                            }}
                          >
                            {rel.type}
                          </span>
                        </td>
                        <td style={{ padding: "0.6rem", fontWeight: 600, color: "#0f172a" }}>{rel.target}</td>
                        <td style={{ padding: "0.6rem" }}>
                          <span
                            style={{
                              color: rel.confidence === "EXACT" ? "#16a34a" : "#2563eb",
                              backgroundColor: rel.confidence === "EXACT" ? "#f0fdf4" : "#eff6ff",
                              padding: "0.15rem 0.45rem",
                              borderRadius: "10px",
                              fontSize: "0.7rem",
                              fontWeight: 700,
                            }}
                          >
                            {rel.confidence}
                          </span>
                        </td>
                        <td style={{ padding: "0.6rem", color: "#64748b" }}>{rel.evidence}</td>
                        <td style={{ padding: "0.6rem" }}>
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
                              Source Record <ExternalLink size={12} />
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

      {/* Interactive Public Knowledge Graph Canvas & Provenance Panel (Phase 6) */}
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
          <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#1e293b", margin: 0, display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Database size={16} color="#7c3aed" /> Interactive Public Knowledge Graph (nexusact_public)
          </h3>
          <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
            Stored Nodes: <strong>{subgraph?.total_nodes || 0}</strong> | Stored Edges: <strong>{subgraph?.total_edges || 0}</strong>
          </span>
        </div>

        {/* Legend and Node Type Filters */}
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center", marginBottom: "1rem" }}>
          <span style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>Filter:</span>
          {["ALL", "PAPER", "MODEL", "PERSON", "ORGANIZATION", "DATASET", "TOPIC"].map((t) => (
            <button
              key={`filter-${t}`}
              onClick={() => setSelectedTypeFilter(t)}
              style={{
                fontSize: "0.72rem",
                fontWeight: 600,
                padding: "0.2rem 0.55rem",
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
              loadPublicGraph();
            }}
            style={{
              fontSize: "0.72rem",
              fontWeight: 600,
              padding: "0.2rem 0.55rem",
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
            <RotateCcw size={11} /> Reset Inspection
          </button>
        </div>

        {/* Graph Canvas Grid & Detail Inspector */}
        <div style={{ display: "grid", gridTemplateColumns: selectedNode || selectedEdge ? "2fr 1fr" : "1fr", gap: "1rem" }}>
          {/* Node Grid Visualization */}
          <div
            style={{
              minHeight: "240px",
              maxHeight: "380px",
              overflowY: "auto",
              border: "1px solid #e2e8f0",
              borderRadius: "6px",
              padding: "0.75rem",
              backgroundColor: "#f8fafc",
            }}
          >
            {filteredNodes.length > 0 ? (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
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
                        padding: "0.35rem 0.7rem",
                        borderRadius: "16px",
                        border: isSelected ? "2px solid #2563eb" : `1px solid ${style.border}`,
                        backgroundColor: style.bg,
                        color: style.text,
                        fontSize: "0.75rem",
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
                No entities match filter '{selectedTypeFilter}'. Run an investigation above to ingest public metadata into FalkorDB.
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
                  <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem", color: "#0f172a", wordBreak: "break-word" }}>
                    {selectedNode.label}
                  </h4>
                  <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.75rem", wordBreak: "break-all" }}>
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
                          .slice(0, 5)
                          .map((e, idx) => (
                            <div
                              key={`conn-edge-${idx}-${e.source}-${e.target}`}
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
                        Isolated entity with no direct edges loaded in subgraph sample.
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
                  <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem", color: "#0f172a" }}>
                    {selectedEdge.type}
                  </h4>
                  <div style={{ fontSize: "0.75rem", color: "#475569", lineHeight: 1.5 }}>
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
                          Provenance Link <ExternalLink size={12} />
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Saved Investigations & Memory (Phase 7) */}
      <div
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "1.25rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#1e293b", margin: 0, display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <History size={16} color="#2563eb" /> Graph-Backed Investigation Memory ({savedInvestigations.length})
          </h3>
          <span style={{ fontSize: "0.78rem", color: "#64748b" }}>
            Persisted in FalkorDB (PublicInvestigation nodes)
          </span>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.85rem", margin: "0 0 1rem 0" }}>
          Completed investigations, evidence chains, and user-confirmed follow-up actions remain preserved in FalkorDB across sessions.
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
                  <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#0f172a" }}>
                    {inv.question}
                  </div>
                  {inv.action_status === "CONFIRMED" && (
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "#15803d", backgroundColor: "#dcfce7", padding: "0.1rem 0.35rem", borderRadius: "4px" }}>
                      ACTION CONFIRMED
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.3rem" }}>
                  {inv.summary}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#2563eb", marginTop: "0.4rem", display: "flex", alignItems: "center", gap: "0.2rem" }}>
                  <LinkIcon size={11} /> Sources: {inv.sources}
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
