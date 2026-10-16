import React, { useState, useEffect } from "react";
import {
  Globe,
  Database,
  BookOpen,
  Network,
  Search,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Cpu,
  Layers,
} from "lucide-react";
import { fetchPublicSources, askUniversalGaf, fetchPublicSubgraph } from "../../api/client";
import type {
  SourceConnectorInfo,
  UniversalInvestigationResult,
  PublicSubgraphResponse,
} from "../../types/discovery";

interface UniversalDiscoveryWorkspaceProps {
  initialMode?: "universal" | "ai_ecosystem" | "research";
}

export const UniversalDiscoveryWorkspace: React.FC<UniversalDiscoveryWorkspaceProps> = ({
  initialMode = "universal",
}) => {
  const [activeTab, setActiveTab] = useState<"universal" | "ai_ecosystem" | "research">(initialMode);
  const [question, setQuestion] = useState("");
  const [sources, setSources] = useState<Record<string, SourceConnectorInfo>>({});
  const [loadingSources, setLoadingSources] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [investigationResult, setInvestigationResult] = useState<UniversalInvestigationResult | null>(null);
  const [subgraph, setSubgraph] = useState<PublicSubgraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Suggested queries by mode
  const suggestedQueries = {
    universal: [
      "Map the open-source AI ecosystem and show connected models, datasets, and organizations.",
      "Which organizations publish models related to transformer architectures?",
      "Which research papers connect attention mechanisms through citations?",
    ],
    ai_ecosystem: [
      "Which datasets are documented as used to train open-source models?",
      "Find Hugging Face models created by major AI research laboratories.",
      "Show models and evaluation datasets linked to llama architectures.",
    ],
    research: [
      "Which institutions are associated with researchers behind transformer papers?",
      "Which papers explicitly reference foundational deep learning publications?",
      "Explore citation relationships between neural network research works.",
    ],
  };

  useEffect(() => {
    loadSources();
    loadPublicGraph();
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
      const g = await fetchPublicSubgraph(50);
      setSubgraph(g);
    } catch (err: unknown) {
      console.warn("Public subgraph load:", err);
    }
  }

  async function handleSearch(queryToRun?: string) {
    const q = queryToRun || question;
    if (!q.trim()) return;

    try {
      setInvestigating(true);
      setError(null);
      let selectedSources: string[] | undefined = undefined;
      if (activeTab === "ai_ecosystem") {
        selectedSources = ["huggingface", "wikidata"];
      } else if (activeTab === "research") {
        selectedSources = ["openalex", "crossref"];
      }

      const res = await askUniversalGaf(q, selectedSources, 5);
      setInvestigationResult(res);
      // Refresh public graph after ingestion
      loadPublicGraph();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Investigation failed";
      setError(msg);
    } finally {
      setInvestigating(false);
    }
  }

  return (
    <div style={{ padding: "1.5rem 2rem", maxWidth: "1400px", margin: "0 auto" }}>
      {/* Header and Sub-tabs */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
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
            Investigate bounded public metadata across AI models, datasets, research papers, organizations, and citations in FalkorDB.
          </p>
        </div>

        {/* Sub-mode selector */}
        <div
          style={{
            display: "flex",
            backgroundColor: "#f1f5f9",
            borderRadius: "8px",
            padding: "0.25rem",
            gap: "0.25rem",
          }}
        >
          <button
            onClick={() => setActiveTab("universal")}
            style={{
              padding: "0.45rem 0.9rem",
              borderRadius: "6px",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              backgroundColor: activeTab === "universal" ? "#ffffff" : "transparent",
              color: activeTab === "universal" ? "#2563eb" : "#64748b",
              boxShadow: activeTab === "universal" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Network size={15} /> Universal Ask GAF
          </button>
          <button
            onClick={() => setActiveTab("ai_ecosystem")}
            style={{
              padding: "0.45rem 0.9rem",
              borderRadius: "6px",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              backgroundColor: activeTab === "ai_ecosystem" ? "#ffffff" : "transparent",
              color: activeTab === "ai_ecosystem" ? "#2563eb" : "#64748b",
              boxShadow: activeTab === "ai_ecosystem" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Cpu size={15} /> AI Ecosystem
          </button>
          <button
            onClick={() => setActiveTab("research")}
            style={{
              padding: "0.45rem 0.9rem",
              borderRadius: "6px",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              backgroundColor: activeTab === "research" ? "#ffffff" : "transparent",
              color: activeTab === "research" ? "#2563eb" : "#64748b",
              boxShadow: activeTab === "research" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <BookOpen size={15} /> Research & Citations
          </button>
        </div>
      </div>

      {/* Source Connectors Health Bar */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "0.75rem",
          marginBottom: "1.5rem",
        }}
      >
        {loadingSources ? (
          <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Checking approved public source connectors...</div>
        ) : (
          Object.values(sources).map((conn) => (
            <div
              key={conn.source_id}
              style={{
                backgroundColor: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                padding: "0.75rem 1rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b" }}>{conn.display_name}</div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                  Entities: {conn.entity_types.join(", ")}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                {conn.healthy ? (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.25rem",
                      fontSize: "0.75rem",
                      color: "#16a34a",
                      backgroundColor: "#f0fdf4",
                      padding: "0.2rem 0.5rem",
                      borderRadius: "12px",
                      fontWeight: 600,
                    }}
                  >
                    <CheckCircle2 size={12} /> ONLINE
                  </span>
                ) : (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.25rem",
                      fontSize: "0.75rem",
                      color: "#dc2626",
                      backgroundColor: "#fef2f2",
                      padding: "0.2rem 0.5rem",
                      borderRadius: "12px",
                      fontWeight: 600,
                    }}
                  >
                    <AlertTriangle size={12} /> DEGRADED
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Query Bar */}
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
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder={
              activeTab === "universal"
                ? "Ask GAF anything across AI models, datasets, papers, and organizations..."
                : activeTab === "ai_ecosystem"
                ? "Search AI models, datasets, or organizations (e.g. meta-llama/Llama-3-8B)..."
                : "Search research papers, authors, citations, or topics (e.g. attention mechanism)..."
            }
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
          {suggestedQueries[activeTab].map((sq, idx) => (
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

      {/* Investigation Results */}
      {investigationResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", marginBottom: "2rem" }}>
          {/* Summary Banner */}
          <div
            style={{
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              padding: "1rem 1.25rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div>
              <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>INVESTIGATION SUMMARY</div>
              <div style={{ fontSize: "1rem", fontWeight: 600, color: "#1e293b", marginTop: "0.2rem" }}>
                {investigationResult.summary}
              </div>
            </div>
            <div style={{ display: "flex", gap: "1.5rem" }}>
              <div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Entities Ingested</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#2563eb" }}>
                  {investigationResult.records_ingested}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Relationships</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#16a34a" }}>
                  {investigationResult.relationships.length}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Execution Time</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#7c3aed" }}>
                  {(investigationResult.execution_time_ms / 1000).toFixed(2)}s
                </div>
              </div>
            </div>
          </div>

          {/* Discovered Relationships Table with Provenance */}
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
                      <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
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

          {/* Discovered Entities */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              padding: "1.25rem",
            }}
          >
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#1e293b", margin: "0 0 1rem 0" }}>
              Ingested Public Entities ({investigationResult.entities.length})
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: "0.75rem",
              }}
            >
              {investigationResult.entities.map((ent, idx) => (
                <div
                  key={idx}
                  style={{
                    border: "1px solid #e2e8f0",
                    borderRadius: "6px",
                    padding: "0.75rem",
                    backgroundColor: "#f8fafc",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontWeight: 700,
                        color: "#2563eb",
                        backgroundColor: "#eff6ff",
                        padding: "0.15rem 0.4rem",
                        borderRadius: "4px",
                      }}
                    >
                      {ent.type.toUpperCase()}
                    </span>
                    <span style={{ fontSize: "0.7rem", color: "#64748b" }}>{ent.source}</span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b", marginTop: "0.4rem" }}>
                    {ent.name}
                  </div>
                  {ent.url && (
                    <a
                      href={ent.url}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.2rem",
                        fontSize: "0.75rem",
                        color: "#2563eb",
                        marginTop: "0.3rem",
                        textDecoration: "none",
                      }}
                    >
                      View at source <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Coverage & Limitations Note */}
          {investigationResult.coverage_limitations.length > 0 && (
            <div
              style={{
                backgroundColor: "#fffbeb",
                border: "1px solid #fef3c7",
                borderRadius: "8px",
                padding: "1rem",
                color: "#92400e",
                fontSize: "0.85rem",
              }}
            >
              <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.4rem" }}>
                <AlertTriangle size={15} /> Coverage Disclosures & Scope Limitations
              </div>
              <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: "1.5" }}>
                {investigationResult.coverage_limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Public Knowledge Graph Overview (FalkorDB) */}
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
            <Database size={16} color="#7c3aed" /> Persistent Public Graph in FalkorDB (nexusact_public)
          </h3>
          <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
            Stored Nodes: {subgraph?.total_nodes || 0} | Stored Edges: {subgraph?.total_edges || 0}
          </span>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.85rem", margin: "0 0 1rem 0" }}>
          All bounded public discoveries are persisted idempotently into FalkorDB. Multi-hop queries and shortest paths can traverse across models, papers, and organizations.
        </p>
        {subgraph && subgraph.nodes.length > 0 ? (
          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
            {subgraph.nodes.slice(0, 20).map((n) => (
              <span
                key={n.id}
                style={{
                  fontSize: "0.75rem",
                  backgroundColor: "#f1f5f9",
                  border: "1px solid #cbd5e1",
                  borderRadius: "14px",
                  padding: "0.2rem 0.6rem",
                  color: "#334155",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                }}
              >
                <Layers size={11} color="#64748b" /> {n.label} ({n.type})
              </span>
            ))}
            {subgraph.nodes.length > 20 && (
              <span style={{ fontSize: "0.75rem", color: "#64748b", alignSelf: "center" }}>
                +{subgraph.nodes.length - 20} more in database
              </span>
            )}
          </div>
        ) : (
          <div style={{ color: "#94a3b8", fontSize: "0.85rem", fontStyle: "italic" }}>
            Public graph is currently empty. Run an investigation above to ingest public metadata into FalkorDB.
          </div>
        )}
      </div>
    </div>
  );
};
