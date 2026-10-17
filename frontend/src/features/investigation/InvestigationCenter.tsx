import React, { useState, useEffect } from "react";
import {
  GitBranch,
  ShieldAlert,
  DollarSign,
  ArrowRight,
  Database,
  FolderGit2,
  CheckCircle2,
  RotateCw,
  Compass,
} from "lucide-react";
import { fetchSavedInvestigations, fetchRepositories } from "../../api/client";
import type { SavedInvestigation } from "../../types/discovery";
import type { RepositoryRecord } from "../../types/investigation";
import type { InvestigationMode } from "./InvestigationWorkspace";

export interface InvestigationCenterProps {
  selectedRepoId: string;
  onSelectRepoId: (repoId: string) => void;
  onLaunchWorkflow: (
    mode: InvestigationMode,
    tab: "graph" | "code" | "security" | "fraud",
    repoId?: string
  ) => void;
}

export const InvestigationCenter: React.FC<InvestigationCenterProps> = ({
  selectedRepoId,
  onSelectRepoId,
  onLaunchWorkflow,
}) => {
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [savedInvestigations, setSavedInvestigations] = useState<SavedInvestigation[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    loadRepos();
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadRepos() {
    try {
      const repos = await fetchRepositories();
      setRepositories(repos);
      if (repos.length > 0 && !repos.some((r) => r.id === selectedRepoId)) {
        onSelectRepoId(repos[0].id);
      }
    } catch (err) {
      console.warn("Could not load repositories in InvestigationCenter:", err);
    }
  }

  async function loadHistory() {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const res = await fetchSavedInvestigations(10);
      setSavedInvestigations(res.investigations || []);
    } catch (err: unknown) {
      console.warn("Could not load saved investigations:", err);
      setHistoryError(err instanceof Error ? err.message : "Failed to load past investigations");
    } finally {
      setIsLoadingHistory(false);
    }
  }

  const activeRepo = repositories.find((r) => r.id === selectedRepoId);

  return (
    <div
      style={{
        maxWidth: "1400px",
        margin: "0 auto",
        padding: "1.5rem 2rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.75rem",
      }}
    >
      {/* ── Top Header & Context Bar ── */}
      <div
        style={{
          backgroundColor: "var(--bg-card)",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle)",
          padding: "1.5rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1.25rem",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.35rem" }}>
            <Compass size={22} color="var(--accent-blue)" />
            <h1 style={{ fontSize: "1.35rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
              Investigation Center
            </h1>
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: 700,
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
                backgroundColor: "var(--accent-blue-subtle)",
                color: "var(--accent-blue)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              GraphAction Fabric (GAF)
            </span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0, maxWidth: "720px" }}>
            Launch or resume graph-backed investigations with verified evidence grounding across codebase architecture,
            known security advisories, and isolated transaction topologies.
          </p>
        </div>

        {/* Selected Repository Control */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            backgroundColor: "var(--bg-secondary)",
            padding: "0.6rem 1rem",
            borderRadius: "8px",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <FolderGit2 size={16} color="var(--text-secondary)" />
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Target Repository
            </span>
            <select
              value={selectedRepoId}
              onChange={(e) => onSelectRepoId(e.target.value)}
              style={{
                background: "transparent",
                border: "none",
                fontSize: "0.85rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                cursor: "pointer",
                padding: 0,
                outline: "none",
              }}
            >
              {repositories.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.name} ({repo.id})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ── Three Primary Workflow Cards ── */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.85rem" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
            Investigation Workflows
          </h2>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Select an operational investigation mode to explore verified connected data
          </span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
            gap: "1.25rem",
          }}
        >
          {/* Workflow 1: Codebase Walkthrough */}
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 0.15s ease, border-color 0.15s ease",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                <div
                  style={{
                    width: "38px",
                    height: "38px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(59, 130, 246, 0.12)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <GitBranch size={20} color="#2563eb" />
                </div>
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    padding: "0.15rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor: "var(--bg-secondary)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  Codebase Topology
                </span>
              </div>

              <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.4rem" }}>
                Codebase Walkthrough
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.45, marginBottom: "1rem" }}>
                Understand how actual components and execution paths relate across the repository. Inspect caller-callee
                relationships, symbols, source code files, and blast radius.
              </p>

              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  backgroundColor: "var(--bg-secondary)",
                  padding: "0.6rem 0.75rem",
                  borderRadius: "6px",
                  marginBottom: "1.25rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.3rem",
                }}
              >
                <div>
                  <strong>Active Target:</strong> {activeRepo?.name || selectedRepoId}
                </div>
                <div>
                  <strong>Primary Features:</strong> GraphCanvas, Code Inspector, Blast Radius
                </div>
              </div>
            </div>

            <button
              onClick={() => onLaunchWorkflow("codebase_walkthrough", "graph")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                width: "100%",
                padding: "0.65rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "var(--accent-blue)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
                transition: "background 0.15s ease",
              }}
            >
              Launch Codebase Walkthrough
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Workflow 2: Security Triage */}
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 0.15s ease, border-color 0.15s ease",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                <div
                  style={{
                    width: "38px",
                    height: "38px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <ShieldAlert size={20} color="#dc2626" />
                </div>
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    padding: "0.15rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor: "rgba(239, 68, 68, 0.08)",
                    color: "#dc2626",
                    border: "1px solid rgba(239, 68, 68, 0.2)",
                  }}
                >
                  Advisories & Impact
                </span>
              </div>

              <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.4rem" }}>
                Security Vulnerability Triage
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.45, marginBottom: "1rem" }}>
                Investigate dependency advisories from the OSV database, identify affected software components, and trace
                evidence-backed impact to evaluate real blast radius.
              </p>

              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  backgroundColor: "var(--bg-secondary)",
                  padding: "0.6rem 0.75rem",
                  borderRadius: "6px",
                  marginBottom: "1.25rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.3rem",
                }}
              >
                <div>
                  <strong>Database:</strong> OSV Vulnerability Intelligence
                </div>
                <div>
                  <strong>Primary Features:</strong> Transitive Advisory Mapping, Severity Triage
                </div>
              </div>
            </div>

            <button
              onClick={() => onLaunchWorkflow("security_triage", "security")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                width: "100%",
                padding: "0.65rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "#dc2626",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
                transition: "background 0.15s ease",
              }}
            >
              Launch Security Triage
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Workflow 3: Fraud Investigation */}
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 0.15s ease, border-color 0.15s ease",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                <div
                  style={{
                    width: "38px",
                    height: "38px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(16, 185, 129, 0.12)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <DollarSign size={20} color="#059669" />
                </div>
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    padding: "0.15rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor: "rgba(16, 185, 129, 0.08)",
                    color: "#059669",
                    border: "1px solid rgba(16, 185, 129, 0.2)",
                  }}
                >
                  Isolated Graph
                </span>
              </div>

              <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.4rem" }}>
                Fraud Investigation
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.45, marginBottom: "1rem" }}>
                Investigate connected transaction patterns in the isolated synthetic fraud graph (
                <code style={{ fontSize: "0.76rem" }}>nexusact_fraud_demo</code>). Trace shared devices, rapid fund transfers,
                and circular mule rings.
              </p>

              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  backgroundColor: "var(--bg-secondary)",
                  padding: "0.6rem 0.75rem",
                  borderRadius: "6px",
                  marginBottom: "1.25rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.3rem",
                }}
              >
                <div>
                  <strong>Environment:</strong> Isolated FalkorDB Fraud Graph
                </div>
                <div>
                  <strong>Primary Features:</strong> Circular Flow Detection, Risk Scoring
                </div>
              </div>
            </div>

            <button
              onClick={() => onLaunchWorkflow("fraud_demo", "fraud")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                width: "100%",
                padding: "0.65rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "#059669",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
                transition: "background 0.15s ease",
              }}
            >
              Launch Fraud Investigation
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Recent Investigations (Persistent FalkorDB Graph Memory) ── */}
      <div
        style={{
          backgroundColor: "var(--bg-card)",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle)",
          padding: "1.5rem",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "1.25rem",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          <div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
              Recent Graph Investigations
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "0.2rem 0 0 0" }}>
              Persistent investigation memory retrieved directly from FalkorDB. Opening an investigation restores its
              context and findings.
            </p>
          </div>

          <button
            onClick={loadHistory}
            disabled={isLoadingHistory}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              padding: "0.35rem 0.75rem",
              borderRadius: "5px",
              border: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-secondary)",
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            <RotateCw size={13} style={{ animation: isLoadingHistory ? "spin 1.5s linear infinite" : undefined }} />
            Refresh
          </button>
        </div>

        {isLoadingHistory ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
            <RotateCw size={24} style={{ animation: "spin 1.5s linear infinite", marginBottom: "0.5rem" }} />
            <p style={{ fontSize: "0.85rem" }}>Loading saved investigations from FalkorDB...</p>
          </div>
        ) : historyError ? (
          <div
            style={{
              padding: "1rem",
              borderRadius: "6px",
              backgroundColor: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              color: "#dc2626",
              fontSize: "0.82rem",
            }}
          >
            {historyError}
          </div>
        ) : savedInvestigations.length === 0 ? (
          <div
            style={{
              padding: "2.5rem 1rem",
              textAlign: "center",
              border: "1px dashed var(--border-subtle)",
              borderRadius: "8px",
              backgroundColor: "var(--bg-secondary)",
            }}
          >
            <Database size={32} color="var(--text-muted)" style={{ marginBottom: "0.5rem" }} />
            <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
              No Investigations Recorded in Graph Memory
            </h4>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
              Launch one of the workflows above to conduct an investigation and persist its reasoning in FalkorDB.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.82rem",
                textAlign: "left",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--border-subtle)",
                    backgroundColor: "var(--bg-secondary)",
                    color: "var(--text-muted)",
                    fontSize: "0.72rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  <th style={{ padding: "0.6rem 0.85rem" }}>Question / Topic</th>
                  <th style={{ padding: "0.6rem 0.85rem" }}>Workflow</th>
                  <th style={{ padding: "0.6rem 0.85rem" }}>Target / Graph</th>
                  <th style={{ padding: "0.6rem 0.85rem" }}>Revision</th>
                  <th style={{ padding: "0.6rem 0.85rem" }}>Timestamp</th>
                  <th style={{ padding: "0.6rem 0.85rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.85rem", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {savedInvestigations.map((inv) => {
                  const mode = inv.input_mode || "codebase_walkthrough";
                  const modeLabel =
                    mode === "security_triage"
                      ? "Security Triage"
                      : mode === "fraud_demo"
                      ? "Fraud Demo"
                      : "Codebase Walkthrough";
                  const targetGraph = inv.repository_id || inv.graph_name || "nexusact_main";
                  const commitSha = inv.commit_sha ? inv.commit_sha.slice(0, 8) : "—";
                  const dateStr = inv.created_at
                    ? new Date(inv.created_at * 1000).toLocaleString(undefined, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : "—";

                  return (
                    <tr
                      key={inv.investigation_id}
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        transition: "background 0.1s ease",
                      }}
                    >
                      <td style={{ padding: "0.75rem 0.85rem", maxWidth: "340px" }}>
                        <div style={{ fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {inv.question}
                        </div>
                        {inv.summary && (
                          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {inv.summary}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", whiteSpace: "nowrap" }}>
                        <span
                          style={{
                            fontSize: "0.72rem",
                            padding: "0.15rem 0.45rem",
                            borderRadius: "4px",
                            backgroundColor:
                              mode === "security_triage"
                                ? "rgba(239, 68, 68, 0.1)"
                                : mode === "fraud_demo"
                                ? "rgba(16, 185, 129, 0.1)"
                                : "rgba(59, 130, 246, 0.1)",
                            color:
                              mode === "security_triage"
                                ? "#dc2626"
                                : mode === "fraud_demo"
                                ? "#059669"
                                : "var(--accent-blue)",
                            fontWeight: 600,
                          }}
                        >
                          {modeLabel}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {targetGraph}
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {commitSha}
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", fontSize: "0.75rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {dateStr}
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", whiteSpace: "nowrap" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            fontSize: "0.72rem",
                            fontWeight: 600,
                            color: inv.action_status === "CONFIRMED" ? "#059669" : "var(--text-muted)",
                          }}
                        >
                          <CheckCircle2 size={12} color={inv.action_status === "CONFIRMED" ? "#059669" : "var(--text-muted)"} />
                          {inv.action_status || "COMPLETED"}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem 0.85rem", textAlign: "right", whiteSpace: "nowrap" }}>
                        <button
                          onClick={() => {
                            const targetTab =
                              mode === "security_triage"
                                ? "security"
                                : mode === "fraud_demo"
                                ? "fraud"
                                : "graph";
                            const targetMode: InvestigationMode =
                              mode === "security_triage"
                                ? "security_triage"
                                : mode === "fraud_demo"
                                ? "fraud_demo"
                                : "codebase_walkthrough";
                            onLaunchWorkflow(targetMode, targetTab, inv.repository_id || undefined);
                          }}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            padding: "0.3rem 0.65rem",
                            borderRadius: "4px",
                            border: "1px solid var(--accent-blue)",
                            backgroundColor: "var(--accent-blue-subtle)",
                            color: "var(--accent-blue)",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          Open
                          <ArrowRight size={12} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
