/**
 * FraudInvestigationPanel — Real-Data Transaction Network Investigation for NexusAct.
 *
 * Implements Phase 21:
 *   - User-driven real transaction dataset ingestion (CSV/JSON upload & schema mapping).
 *   - Graph isolation in FalkorDB namespaces (`fin_<dataset_id>`).
 *   - Direct Cypher graph reasoning: multi-hop circular routing, shared devices/IPs, velocity bursts.
 *   - Transparent, mathematical risk scoring (never hardcoded or uncalibrated).
 *   - Visual semantics: Account (#2563eb), Transaction (#7c3aed), Device (#0d9488), IP (#d97706), Merchant (#16a34a).
 *   - Read-only investigation: NO financial mutations or external actions.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  DollarSign,
  Upload,
  Play,
  Layers,
  ShieldCheck,
  ArrowRight,
  Database,
  X,
  Zap,
} from "lucide-react";
import type {
  FinancialDatasetMetadata,
  FinancialInvestigationResult,
  FraudFinding,
  DatasetPreviewResponse,
  ColumnMapping,
  SubgraphResponse,
} from "../../types/investigation";
import {
  fetchFinancialDatasets,
  fetchActiveFinancialDataset,
  activateFinancialDataset,
  previewFinancialDataset,
  ingestFinancialDataset,
  loadSampleBenchmarkDataset,
  investigateFinancialDataset,
  fetchFinancialSubgraph,
} from "../../api/client";
import { GraphCanvas } from "./GraphCanvas";

export interface FraudInvestigationPanelProps {
  onOpenSourceFile?: (filePath: string) => void;
}

export const FraudInvestigationPanel: React.FC<FraudInvestigationPanelProps> = () => {
  // Datasets State
  const [datasets, setDatasets] = useState<FinancialDatasetMetadata[]>([]);
  const [activeDataset, setActiveDataset] = useState<FinancialDatasetMetadata | null>(null);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState<boolean>(true);

  // Investigation State
  const [investigationResult, setInvestigationResult] = useState<FinancialInvestigationResult | null>(null);
  const [isInvestigating, setIsInvestigating] = useState<boolean>(false);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [maxHops, setMaxHops] = useState<number>(4);

  // Subgraph visualization
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [isLoadingSubgraph, setIsLoadingSubgraph] = useState<boolean>(false);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<FraudFinding | null>(null);

  // Upload & Schema Mapping Modal State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [datasetNameInput, setDatasetNameInput] = useState<string>("");
  const [previewData, setPreviewData] = useState<DatasetPreviewResponse | null>(null);
  const [columnMapping, setColumnMapping] = useState<ColumnMapping>({
    tx_id: "",
    src_account: "",
    dst_account: "",
    amount: "",
    timestamp: "",
    currency: "",
    device_id: "",
    ip_address: "",
    merchant_id: "",
    fraud_label: "",
  });
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Load registered datasets
  const loadDatasets = useCallback(async () => {
    try {
      setIsLoadingDatasets(true);
      const dsList = await fetchFinancialDatasets();
      setDatasets(dsList);
      const active = await fetchActiveFinancialDataset();
      setActiveDataset(active);
    } catch (e) {
      console.warn("Could not load financial datasets:", e);
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        setIsLoadingDatasets(true);
        const dsList = await fetchFinancialDatasets();
        if (!isMounted) return;
        setDatasets(dsList);
        const active = await fetchActiveFinancialDataset();
        if (!isMounted) return;
        setActiveDataset(active);
      } catch (e) {
        console.warn("Could not load financial datasets:", e);
      } finally {
        if (isMounted) setIsLoadingDatasets(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    if (activeDataset) {
      (async () => {
        try {
          setIsLoadingSubgraph(true);
          const sg = await fetchFinancialSubgraph(activeDataset.dataset_id, undefined, 2, 80);
          if (isMounted) setSubgraph(sg);
        } catch (e) {
          console.warn("Could not load financial subgraph:", e);
        } finally {
          if (isMounted) setIsLoadingSubgraph(false);
        }
      })();
    } else {
      queueMicrotask(() => {
        if (isMounted) setSubgraph(null);
      });
    }
    return () => {
      isMounted = false;
    };
  }, [activeDataset]);

  // Handle dataset switch
  const handleSelectDataset = async (datasetId: string) => {
    try {
      const activated = await activateFinancialDataset(datasetId);
      setActiveDataset(activated);
      setInvestigationResult(null);
      setHighlightedNodes([]);
      setSelectedFinding(null);
    } catch (e: any) {
      setInvestigationError(e.message || "Failed to switch dataset");
    }
  };

  // Run graph investigation
  const handleRunInvestigation = async () => {
    if (!activeDataset) return;
    try {
      setIsInvestigating(true);
      setInvestigationError(null);
      const res = await investigateFinancialDataset(activeDataset.dataset_id, maxHops);
      setInvestigationResult(res);
      // Auto-highlight first cycle or finding if available
      if (res.findings.length > 0 && res.findings[0].graph_path) {
        setHighlightedNodes(res.findings[0].graph_path);
        setSelectedFinding(res.findings[0]);
      }
    } catch (e: any) {
      setInvestigationError(e.message || "Financial graph investigation failed");
    } finally {
      setIsInvestigating(false);
    }
  };

  // Quick load sample benchmark
  const handleLoadSample = async () => {
    try {
      setIsIngesting(true);
      setUploadError(null);
      const ds = await loadSampleBenchmarkDataset();
      setActiveDataset(ds);
      await loadDatasets();
      // Auto-trigger investigation on sample benchmark
      const res = await investigateFinancialDataset(ds.dataset_id, 4);
      setInvestigationResult(res);
      if (res.findings.length > 0 && res.findings[0].graph_path) {
        setHighlightedNodes(res.findings[0].graph_path);
        setSelectedFinding(res.findings[0]);
      }
    } catch (e: any) {
      setInvestigationError(e.message || "Failed to load sample benchmark");
    } finally {
      setIsIngesting(false);
    }
  };

  // Upload file selection & preview
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadFile(file);
    setDatasetNameInput(file.name.replace(/\.[^/.]+$/, ""));
    setUploadError(null);
    try {
      setIsPreviewing(true);
      const prev = await previewFinancialDataset(file);
      setPreviewData(prev);
      setColumnMapping(prev.suggested_mapping);
    } catch (err: any) {
      setUploadError(err.message || "Failed to parse preview");
    } finally {
      setIsPreviewing(false);
    }
  };

  // Confirm ingestion
  const handleConfirmIngest = async () => {
    if (!uploadFile) return;
    try {
      setIsIngesting(true);
      setUploadError(null);
      const newDs = await ingestFinancialDataset(
        uploadFile,
        datasetNameInput.trim() || uploadFile.name,
        columnMapping
      );
      setActiveDataset(newDs);
      setIsUploadModalOpen(false);
      setUploadFile(null);
      setPreviewData(null);
      await loadDatasets();
    } catch (err: any) {
      setUploadError(err.message || "Ingestion failed");
    } finally {
      setIsIngesting(false);
    }
  };

  // Highlight finding in graph
  const handleSelectFinding = (finding: FraudFinding) => {
    setSelectedFinding(finding);
    if (finding.graph_path && finding.graph_path.length > 0) {
      setHighlightedNodes(finding.graph_path);
    } else if (finding.affected_accounts.length > 0) {
      setHighlightedNodes(finding.affected_accounts);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", width: "100%" }}>
      {/* ── Top Bar: Active Dataset Selector, Provenance & Controls ── */}
      <div
        style={{
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          padding: "1rem 1.25rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <DollarSign size={20} color="#2563eb" />
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
              Fraud Investigation
            </h3>
          </div>

          {/* Dataset Selector Dropdown */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>Dataset:</span>
            <select
              value={activeDataset?.dataset_id || ""}
              onChange={(e) => handleSelectDataset(e.target.value)}
              disabled={isLoadingDatasets || datasets.length === 0}
              style={{
                padding: "0.35rem 0.65rem",
                borderRadius: "5px",
                border: "1px solid var(--border-subtle)",
                fontSize: "0.8rem",
                fontWeight: 600,
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-primary)",
                cursor: "pointer",
                maxWidth: "240px",
              }}
            >
              {datasets.length === 0 ? (
                <option value="">No datasets imported</option>
              ) : (
                datasets.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>
                    {d.dataset_name} ({d.record_count} txs)
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Active Dataset Badges */}
          {activeDataset && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", fontSize: "0.72rem" }}>
              <span
                style={{
                  padding: "0.15rem 0.5rem",
                  borderRadius: "12px",
                  backgroundColor: "rgba(37, 99, 235, 0.1)",
                  color: "#2563eb",
                  fontWeight: 600,
                }}
              >
                Graph: {activeDataset.graph_name}
              </span>
              <span
                style={{
                  padding: "0.15rem 0.5rem",
                  borderRadius: "12px",
                  backgroundColor: "var(--bg-muted)",
                  color: "var(--text-secondary)",
                }}
              >
                {activeDataset.record_count} Transactions • {activeDataset.account_count} Accounts
              </span>
              {activeDataset.has_ground_truth_labels ? (
                <span
                  style={{
                    padding: "0.15rem 0.5rem",
                    borderRadius: "12px",
                    backgroundColor: "#dcfce7",
                    color: "#15803d",
                    fontWeight: 700,
                  }}
                >
                  Ground Truth Labeled
                </span>
              ) : (
                <span
                  style={{
                    padding: "0.15rem 0.5rem",
                    borderRadius: "12px",
                    backgroundColor: "#fef3c7",
                    color: "#b45309",
                  }}
                >
                  Unlabeled
                </span>
              )}
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "0.4rem 0.75rem",
              borderRadius: "5px",
              border: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-primary)",
              color: "var(--text-primary)",
              fontSize: "0.78rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Upload size={14} />
            Import Dataset
          </button>

          <button
            onClick={handleLoadSample}
            disabled={isIngesting}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "0.4rem 0.75rem",
              borderRadius: "5px",
              border: "1px solid #93c5fd",
              backgroundColor: "#eff6ff",
              color: "#1d4ed8",
              fontSize: "0.78rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
            title="Load the verified AML Transaction Benchmark with ground-truth cycle"
          >
            <Zap size={14} color="#1d4ed8" />
            Load Benchmark
          </button>

          {activeDataset && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>Hops:</span>
              <select
                value={maxHops}
                onChange={(e) => setMaxHops(Number(e.target.value))}
                style={{
                  padding: "0.35rem 0.5rem",
                  borderRadius: "5px",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "0.78rem",
                  backgroundColor: "var(--bg-primary)",
                  color: "var(--text-primary)",
                }}
              >
                <option value={3}>3 Hops</option>
                <option value={4}>4 Hops</option>
                <option value={5}>5 Hops</option>
              </select>
              <button
                onClick={handleRunInvestigation}
                disabled={isInvestigating}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.4rem 0.85rem",
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  fontSize: "0.8rem",
                  fontWeight: 700,
                  cursor: isInvestigating ? "not-allowed" : "pointer",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
                }}
              >
                <Play size={14} fill="#ffffff" />
                {isInvestigating ? "Reasoning via FalkorDB..." : "Investigate Dataset"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Empty State: No Dataset Loaded ── */}
      {!activeDataset && (
        <div
          style={{
            padding: "2.5rem 2rem",
            backgroundColor: "var(--bg-card)",
            borderRadius: "8px",
            border: "1px dashed var(--border-strong)",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.85rem",
          }}
        >
          <Database size={44} color="#2563eb" style={{ opacity: 0.8 }} />
          <h4 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
            No Financial Transaction Dataset Loaded
          </h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", maxWidth: "560px", margin: 0 }}>
            NexusAct strictly enforces truthfulness: graph reasoning requires authorized financial data.
            FalkorDB currently contains no active transaction graph. Upload a CSV/JSON file with account
            transfers or load the bundled AML Benchmark to investigate circular movement and shared infrastructure.
          </p>
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
            <button
              onClick={handleLoadSample}
              disabled={isIngesting}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.55rem 1.1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
              }}
            >
              <Zap size={15} />
              Load AML Benchmark Dataset
            </button>
            <button
              onClick={() => setIsUploadModalOpen(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.55rem 1.1rem",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-primary)",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
              }}
            >
              <Upload size={15} />
              Import Custom CSV / JSON
            </button>
          </div>
        </div>
      )}

      {/* ── Active Investigation Content ── */}
      {activeDataset && (
        <>
          {/* Provenance & Read-Only Notice */}
          <div
            style={{
              padding: "0.65rem 1rem",
              borderRadius: "6px",
              backgroundColor: "rgba(37, 99, 235, 0.05)",
              border: "1px solid rgba(37, 99, 235, 0.2)",
              fontSize: "0.76rem",
              color: "var(--text-secondary)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.5rem",
            }}
          >
            <div>
              <strong style={{ color: "var(--text-primary)" }}>Provenance: </strong>
              {activeDataset.provenance_note || "User-authorized transaction records."}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <ShieldCheck size={14} color="#16a34a" />
              <span style={{ color: "#16a34a", fontWeight: 600 }}>Read-Only Analysis</span>
              <span style={{ color: "var(--text-muted)" }}>• No external write mutations</span>
            </div>
          </div>

          {/* Investigation Error Banner */}
          {investigationError && (
            <div
              style={{
                padding: "0.75rem 1rem",
                borderRadius: "6px",
                backgroundColor: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#b91c1c",
                fontSize: "0.8rem",
              }}
            >
              <strong>Investigation Error:</strong> {investigationError}
            </div>
          )}

          {/* Interactive Graph Canvas with Legend */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h4 style={{ fontSize: "0.88rem", fontWeight: 700, margin: 0, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Layers size={16} color="#2563eb" />
                Transaction Network Subgraph ({activeDataset.graph_name})
              </h4>
              {highlightedNodes.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>Traced Path:</span>
                  <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
                    {highlightedNodes.map((n, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          padding: "0.1rem 0.4rem",
                          borderRadius: "4px",
                          backgroundColor: "#fef3c7",
                          color: "#b45309",
                          fontFamily: "var(--font-mono)",
                        }}
                      >
                        {n}
                      </span>
                    ))}
                  </div>
                  <button
                    onClick={() => setHighlightedNodes([])}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
                    title="Clear path highlight"
                  >
                    <X size={13} />
                  </button>
                </div>
              )}
            </div>

            <GraphCanvas
              data={subgraph}
              highlightPathNodes={highlightedNodes}
              isLoading={isLoadingSubgraph}
            />
          </div>

          {/* Investigation Results Section */}
          {investigationResult && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* Transparent Risk Score Breakdown */}
              <div
                style={{
                  padding: "1rem",
                  borderRadius: "8px",
                  backgroundColor: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div>
                    <h4 style={{ fontSize: "0.92rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                      FalkorDB Risk Factor Decomposition
                    </h4>
                    <p style={{ fontSize: "0.76rem", color: "var(--text-secondary)", margin: "0.2rem 0 0 0" }}>
                      Transparent mathematical scoring derived directly from verified Cypher graph queries.
                    </p>
                  </div>
                  <div
                    style={{
                      padding: "0.3rem 0.8rem",
                      borderRadius: "20px",
                      backgroundColor:
                        investigationResult.risk_score >= 0.65
                          ? "#fee2e2"
                          : investigationResult.risk_score >= 0.35
                          ? "#fef3c7"
                          : "#dcfce7",
                      color:
                        investigationResult.risk_score >= 0.65
                          ? "#b91c1c"
                          : investigationResult.risk_score >= 0.35
                          ? "#b45309"
                          : "#15803d",
                      fontWeight: 700,
                      fontSize: "0.85rem",
                    }}
                  >
                    Composite Risk Score: {(investigationResult.risk_score * 100).toFixed(0)}%
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {investigationResult.risk_factors.map((rf, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: "0.76rem",
                        padding: "0.4rem 0.65rem",
                        borderRadius: "5px",
                        backgroundColor: "var(--bg-muted)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div>
                        <strong style={{ color: "var(--text-primary)" }}>{rf.factor_name.replace(/_/g, " ")}</strong>
                        <span style={{ color: "var(--text-muted)", marginLeft: "0.5rem" }}>— {rf.supporting_evidence}</span>
                      </div>
                      <div style={{ fontWeight: 700, color: "#b91c1c", fontFamily: "var(--font-mono)" }}>
                        +{(rf.contribution * 100).toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>

                {/* Ground Truth Evaluation if Available */}
                {investigationResult.ground_truth_comparison && (
                  <div
                    style={{
                      marginTop: "0.85rem",
                      padding: "0.65rem 0.85rem",
                      borderRadius: "6px",
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      fontSize: "0.76rem",
                      color: "#166534",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "0.5rem",
                    }}
                  >
                    <div>
                      <strong>Ground Truth Benchmark Evaluation: </strong>
                      {investigationResult.ground_truth_comparison.evaluation_notes}
                    </div>
                    <div style={{ display: "flex", gap: "0.8rem", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      <span>Precision: {(investigationResult.ground_truth_comparison.precision * 100).toFixed(1)}%</span>
                      <span>Recall: {(investigationResult.ground_truth_comparison.recall * 100).toFixed(1)}%</span>
                      <span>F1: {(investigationResult.ground_truth_comparison.f1_score * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Detected Findings List */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <h4 style={{ fontSize: "0.92rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                  Verified Graph Findings ({investigationResult.findings.length})
                </h4>

                {investigationResult.findings.map((f) => {
                  const isSelected = selectedFinding?.finding_id === f.finding_id;
                  return (
                    <div
                      key={f.finding_id}
                      onClick={() => handleSelectFinding(f)}
                      style={{
                        padding: "1rem",
                        borderRadius: "8px",
                        border: `1.5px solid ${isSelected ? "#2563eb" : "var(--border-subtle)"}`,
                        backgroundColor: isSelected ? "rgba(37, 99, 235, 0.03)" : "var(--bg-card)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              padding: "0.15rem 0.45rem",
                              borderRadius: "4px",
                              backgroundColor: f.confidence_score >= 0.75 ? "#fee2e2" : "#fef3c7",
                              color: f.confidence_score >= 0.75 ? "#b91c1c" : "#b45309",
                            }}
                          >
                            {f.category.replace(/_/g, " ")}
                          </span>
                          <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{f.title}</strong>
                        </div>
                        {f.amounts_involved_usd > 0 && (
                          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary)" }}>
                            Volume: ${f.amounts_involved_usd.toLocaleString()}
                          </span>
                        )}
                      </div>

                      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "0.45rem 0" }}>
                        {f.plain_explanation}
                      </p>

                      {/* Path Nodes with 1-Click Highlight */}
                      {f.graph_path && f.graph_path.length > 0 && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.4rem" }}>
                          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Directed Path:</span>
                          {f.graph_path.map((nodeId, idx) => (
                            <React.Fragment key={idx}>
                              <span
                                style={{
                                  padding: "0.15rem 0.45rem",
                                  borderRadius: "4px",
                                  backgroundColor: "var(--bg-muted)",
                                  border: "1px solid var(--border-subtle)",
                                  fontSize: "0.72rem",
                                  fontFamily: "var(--font-mono)",
                                  fontWeight: 600,
                                }}
                              >
                                {nodeId}
                              </span>
                              {idx < f.graph_path!.length - 1 && <ArrowRight size={11} color="var(--text-muted)" />}
                            </React.Fragment>
                          ))}
                        </div>
                      )}

                      {/* Cypher Query Inspector */}
                      {isSelected && (
                        <div style={{ marginTop: "0.75rem", paddingTop: "0.6rem", borderTop: "1px solid var(--border-subtle)" }}>
                          <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: "0.25rem" }}>
                            Executed FalkorDB Cypher Query:
                          </div>
                          <pre
                            style={{
                              fontSize: "0.72rem",
                              fontFamily: "var(--font-mono)",
                              padding: "0.55rem 0.75rem",
                              borderRadius: "5px",
                              backgroundColor: "var(--bg-primary)",
                              border: "1px solid var(--border-subtle)",
                              color: "var(--text-primary)",
                              margin: 0,
                              overflowX: "auto",
                            }}
                          >
                            {f.supporting_cypher}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Benign Controls Suppression Summary */}
              {investigationResult.benign_controls && investigationResult.benign_controls.length > 0 && (
                <div
                  style={{
                    padding: "1rem",
                    borderRadius: "8px",
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <h4 style={{ fontSize: "0.88rem", fontWeight: 700, margin: "0 0 0.5rem 0", color: "#16a34a", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <ShieldCheck size={16} color="#16a34a" />
                    Verified Benign Control Accounts (False-Positive Suppression)
                  </h4>
                  <p style={{ fontSize: "0.76rem", color: "var(--text-secondary)", margin: "0 0 0.65rem 0" }}>
                    Accounts evaluated by FalkorDB graph queries that did not participate in circular routing or shared infrastructure.
                  </p>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {investigationResult.benign_controls.map((b, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: "0.4rem 0.65rem",
                          borderRadius: "5px",
                          backgroundColor: "#f0fdf4",
                          border: "1px solid #bbf7d0",
                          fontSize: "0.74rem",
                        }}
                      >
                        <strong style={{ color: "#166534" }}>{b.benign_account_id}</strong>
                        <span style={{ color: "#15803d", marginLeft: "0.4rem" }}>— {b.classification_rationale}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Modal: Dataset Upload & Schema Mapping ── */}
      {isUploadModalOpen && (
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
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              boxShadow: "var(--shadow-xl)",
              width: "100%",
              maxWidth: "680px",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                Import Financial Transaction Dataset
              </h3>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Step 1: File Selection */}
            <div>
              <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: "0.35rem" }}>
                Select CSV or JSON File
              </label>
              <input
                type="file"
                accept=".csv,.json"
                onChange={handleFileChange}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  borderRadius: "5px",
                  border: "1px solid var(--border-subtle)",
                  backgroundColor: "var(--bg-primary)",
                  color: "var(--text-primary)",
                  fontSize: "0.8rem",
                }}
              />
              {isPreviewing && (
                <div style={{ fontSize: "0.76rem", color: "#2563eb", marginTop: "0.25rem" }}>
                  Inspecting file schema and profiling columns...
                </div>
              )}
            </div>

            {uploadFile && (
              <div>
                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: "0.35rem" }}>
                  Dataset Name
                </label>
                <input
                  type="text"
                  value={datasetNameInput}
                  onChange={(e) => setDatasetNameInput(e.target.value)}
                  placeholder="e.g., Q3 AML Benchmark"
                  style={{
                    width: "100%",
                    padding: "0.45rem 0.65rem",
                    borderRadius: "5px",
                    border: "1px solid var(--border-subtle)",
                    backgroundColor: "var(--bg-primary)",
                    color: "var(--text-primary)",
                    fontSize: "0.8rem",
                  }}
                />
              </div>
            )}

            {/* Error Display */}
            {uploadError && (
              <div
                style={{
                  padding: "0.65rem",
                  borderRadius: "5px",
                  backgroundColor: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#b91c1c",
                  fontSize: "0.78rem",
                }}
              >
                {uploadError}
              </div>
            )}

            {/* Step 2: Schema Mapping Table */}
            {previewData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <h4 style={{ fontSize: "0.86rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                  Configure Column Mappings ({previewData.detected_columns.length} columns detected)
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                  {(
                    [
                      ["tx_id", "Transaction ID *", true],
                      ["src_account", "Source Account *", true],
                      ["dst_account", "Destination Account *", true],
                      ["amount", "Amount *", true],
                      ["timestamp", "Timestamp", false],
                      ["currency", "Currency", false],
                      ["device_id", "Device ID", false],
                      ["ip_address", "IP Address", false],
                      ["merchant_id", "Merchant ID", false],
                      ["fraud_label", "Fraud Ground Truth", false],
                    ] as const
                  ).map(([fieldKey, labelText, isRequired]) => (
                    <div key={fieldKey} style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                      <span style={{ fontSize: "0.74rem", fontWeight: 600, color: "var(--text-primary)" }}>
                        {labelText}
                      </span>
                      <select
                        value={(columnMapping as any)[fieldKey] || ""}
                        onChange={(e) =>
                          setColumnMapping((prev) => ({ ...prev, [fieldKey]: e.target.value || null }))
                        }
                        style={{
                          padding: "0.35rem 0.5rem",
                          borderRadius: "4px",
                          border: "1px solid var(--border-subtle)",
                          backgroundColor: "var(--bg-primary)",
                          color: "var(--text-primary)",
                          fontSize: "0.76rem",
                        }}
                      >
                        {!isRequired && <option value="">(None)</option>}
                        {previewData.detected_columns.map((col) => (
                          <option key={col} value={col}>
                            {col}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Ingest Button */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", marginTop: "0.5rem" }}>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                style={{
                  padding: "0.45rem 0.9rem",
                  borderRadius: "5px",
                  border: "1px solid var(--border-subtle)",
                  backgroundColor: "var(--bg-primary)",
                  color: "var(--text-secondary)",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmIngest}
                disabled={!uploadFile || isIngesting || !columnMapping.tx_id || !columnMapping.src_account || !columnMapping.dst_account || !columnMapping.amount}
                style={{
                  padding: "0.45rem 1rem",
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: isIngesting ? "not-allowed" : "pointer",
                }}
              >
                {isIngesting ? "Ingesting into FalkorDB..." : "Confirm & Ingest"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
