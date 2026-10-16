import React, { useState } from "react";
import type { IssueProposal, ActionExecutionResult } from "../../types/investigation";
import { proposeAction, executeAction } from "../../api/client";
import { GitPullRequest, ExternalLink, ShieldCheck, AlertCircle, CheckCircle2, Lock } from "lucide-react";

interface IssueProposalCardProps {
  investigationId: string;
  defaultTitle?: string;
  defaultBody?: string;
}

export const IssueProposalCard: React.FC<IssueProposalCardProps> = ({
  investigationId,
  defaultTitle = "[NexusAct] Architecture Impact Report",
  defaultBody = "",
}) => {
  const [proposal, setProposal] = useState<IssueProposal | null>(null);
  const [executionResult, setExecutionResult] = useState<ActionExecutionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [prevInvId, setPrevInvId] = useState(investigationId);
  if (investigationId !== prevInvId) {
    setPrevInvId(investigationId);
    setProposal(null);
    setExecutionResult(null);
    setError(null);
  }

  const handleCreateProposal = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const p = await proposeAction(investigationId, defaultTitle, defaultBody);
      setProposal(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to propose action");
    } finally {
      setIsLoading(false);
    }
  };

  const handleApproveAndExecute = async () => {
    if (!proposal) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await executeAction(proposal.action_id, proposal.payload_hash);
      setExecutionResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Execution failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        backgroundColor: "var(--bg-card)",
        borderRadius: "8px",
        border: "1px solid var(--border-subtle)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem",
          backgroundColor: "var(--bg-muted)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <GitPullRequest size={16} color="var(--accent-blue)" />
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Verified Action & GitHub Issue Proposal
          </h3>
        </div>
        {proposal && (
          <span
            style={{
              fontSize: "0.7rem",
              fontFamily: "var(--font-mono)",
              backgroundColor: "var(--bg-secondary)",
              padding: "0.15rem 0.45rem",
              borderRadius: "4px",
              border: "1px solid var(--border-subtle)",
            }}
          >
            {proposal.state}
          </span>
        )}
      </div>

      <div style={{ padding: "1rem" }}>
        {error && (
          <div
            style={{
              padding: "0.5rem 0.75rem",
              backgroundColor: "var(--status-contradicted-bg)",
              border: "1px solid var(--status-contradicted-border)",
              borderRadius: "4px",
              color: "var(--status-contradicted-text)",
              fontSize: "0.78rem",
              marginBottom: "0.75rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {!proposal ? (
          <div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
              Generate an evidence-backed GitHub issue proposal derived strictly from verified FalkorDB graph findings.
            </p>
            <button
              onClick={handleCreateProposal}
              disabled={isLoading}
              style={{
                backgroundColor: "var(--accent-blue)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                padding: "0.45rem 1rem",
                fontSize: "0.8rem",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
              }}
            >
              <GitPullRequest size={14} />
              {isLoading ? "Generating Proposal..." : "Preview Issue Proposal"}
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div>
              <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block" }}>
                Title
              </label>
              <div
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  backgroundColor: "var(--bg-muted)",
                  padding: "0.45rem 0.75rem",
                  borderRadius: "4px",
                  marginTop: "0.2rem",
                }}
              >
                {proposal.title}
              </div>
            </div>

            <div>
              <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", display: "block" }}>
                Markdown Body (with GAF Idempotency Marker)
              </label>
              <pre
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-secondary)",
                  backgroundColor: "var(--bg-muted)",
                  padding: "0.6rem 0.75rem",
                  borderRadius: "4px",
                  maxHeight: "180px",
                  overflowY: "auto",
                  marginTop: "0.2rem",
                  whiteSpace: "pre-wrap",
                }}
              >
                {proposal.body}
              </pre>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                fontSize: "0.72rem",
                color: "var(--text-muted)",
                backgroundColor: "#fafafa",
                padding: "0.4rem 0.6rem",
                borderRadius: "4px",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <span>Canonical Hash: <code style={{ color: "var(--accent-blue)" }}>{proposal.payload_hash.slice(0, 16)}...</code></span>
              <span>Target: <strong>{proposal.target_repository}</strong></span>
            </div>

            {/* Execution / Submission Outcome */}
            {executionResult ? (
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "6px",
                  backgroundColor:
                    executionResult.state === "VERIFIED"
                      ? "var(--status-verified-bg)"
                      : "var(--status-contradicted-bg)",
                  border: `1px solid ${
                    executionResult.state === "VERIFIED"
                      ? "var(--status-verified-border)"
                      : "var(--status-contradicted-border)"
                  }`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.3rem" }}>
                  <CheckCircle2
                    size={16}
                    color={
                      executionResult.state === "VERIFIED"
                        ? "var(--status-verified-text)"
                        : "var(--status-contradicted-text)"
                    }
                  />
                  <strong
                    style={{
                      fontSize: "0.82rem",
                      color:
                        executionResult.state === "VERIFIED"
                          ? "var(--status-verified-text)"
                          : "var(--status-contradicted-text)",
                    }}
                  >
                    Action State: {executionResult.state}
                  </strong>
                </div>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                  {executionResult.message}
                </p>
                {executionResult.external_issue_url && (
                  <a
                    href={executionResult.external_issue_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.3rem",
                      fontSize: "0.78rem",
                      marginTop: "0.4rem",
                      fontWeight: 600,
                    }}
                  >
                    View Issue #{executionResult.external_issue_id} on GitHub <ExternalLink size={12} />
                  </a>
                )}
              </div>
            ) : (
              <div>
                {!proposal.can_execute ? (
                  <div
                    style={{
                      padding: "0.5rem 0.75rem",
                      backgroundColor: "var(--status-unknown-bg)",
                      border: "1px solid var(--status-unknown-border)",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      color: "var(--status-unknown-text)",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <Lock size={14} />
                    <span>{proposal.reason}</span>
                  </div>
                ) : (
                  <button
                    onClick={handleApproveAndExecute}
                    disabled={isLoading}
                    style={{
                      backgroundColor: "var(--accent-blue)",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      padding: "0.5rem 1.25rem",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <ShieldCheck size={14} />
                    {isLoading ? "Submitting & Verifying..." : "Approve & Submit to GitHub"}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
