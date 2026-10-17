import React, { useState, useEffect } from "react";
import type { PanelExplanationResponse } from "../../types/investigation";
import { fetchPanelExplanation } from "../../api/client";
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  RotateCw,
  ShieldCheck,
  CheckCircle2,
  HelpCircle,
  ArrowRight,
  Info,
} from "lucide-react";

export interface PanelExplanationProps {
  investigationId: string;
  panelId: string;
  question: string;
  targetId?: string;
  repoId?: string;
  commitSha?: string;
  dataSummary: Record<string, unknown>;
  defaultExpanded?: boolean;
}

export const PanelExplanation: React.FC<PanelExplanationProps> = ({
  investigationId,
  panelId,
  question,
  targetId,
  repoId,
  commitSha,
  dataSummary,
  defaultExpanded = false,
}) => {
  const [explanation, setExplanation] = useState<PanelExplanationResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [error, setError] = useState<string | null>(null);

  const dataSummaryStr = JSON.stringify(dataSummary);

  useEffect(() => {
    let isMounted = true;
    if (!investigationId || !panelId) return;

    Promise.resolve().then(() => {
      if (!isMounted) return;
      setIsLoading(true);
      setError(null);

      fetchPanelExplanation({
        investigation_id: investigationId,
        panel_id: panelId,
        question: question || "Codebase investigation",
        target_id: targetId,
        repo_id: repoId,
        commit_sha: commitSha,
        data_summary: dataSummary,
      })
        .then((res) => {
          if (isMounted) setExplanation(res);
        })
        .catch((err) => {
          if (isMounted) {
            console.warn(`Explanation failed for ${panelId}:`, err);
            setError("Explanation temporarily unavailable.");
          }
        })
        .finally(() => {
          if (isMounted) setIsLoading(false);
        });
    });

    return () => {
      isMounted = false;
    };
  }, [investigationId, panelId, question, targetId, repoId, commitSha, dataSummaryStr, dataSummary]);

  const handleManualRefresh = () => {
    if (!investigationId || !panelId) return;
    setIsLoading(true);
    setError(null);
    fetchPanelExplanation({
      investigation_id: investigationId,
      panel_id: panelId,
      question: question || "Codebase investigation",
      target_id: targetId,
      repo_id: repoId,
      commit_sha: commitSha,
      data_summary: dataSummary,
    })
      .then((res) => setExplanation(res))
      .catch((err) => {
        console.warn(`Explanation refresh failed for ${panelId}:`, err);
        setError("Explanation temporarily unavailable.");
      })
      .finally(() => setIsLoading(false));
  };

  if (isLoading && !explanation) {
    return (
      <div
        style={{
          padding: "0.6rem 0.85rem",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          marginBottom: "1rem",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          fontSize: "0.78rem",
          color: "var(--text-muted)",
        }}
      >
        <RotateCw size={13} style={{ animation: "spin 1.5s linear infinite", color: "var(--accent-blue)" }} />
        <span>Generating evidence-grounded explanation...</span>
      </div>
    );
  }

  if (error && !explanation) {
    return null;
  }

  if (!explanation) return null;

  const isGemini = explanation.provider_status === "gemini";
  const isCached = explanation.provider_status === "cached";

  return (
    <div
      style={{
        backgroundColor: "var(--bg-card)",
        borderRadius: "8px",
        border: "1px solid var(--border-subtle)",
        borderLeft: isGemini ? "3px solid #6366f1" : "3px solid var(--accent-blue)",
        boxShadow: "var(--shadow-sm)",
        marginBottom: "1rem",
        overflow: "hidden",
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          padding: "0.65rem 0.95rem",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "0.75rem",
          backgroundColor: "var(--bg-secondary)",
          borderBottom: isExpanded ? "1px solid var(--border-subtle)" : "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", flex: 1 }}>
          <Sparkles
            size={16}
            color={isGemini ? "#6366f1" : "var(--accent-blue)"}
            style={{ marginTop: "2px", flexShrink: 0 }}
          />
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <span style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-primary)" }}>
                Graph Intelligence Insight
              </span>
              <span
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 600,
                  padding: "0.1rem 0.45rem",
                  borderRadius: "4px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  backgroundColor: isGemini
                    ? "rgba(99, 102, 241, 0.12)"
                    : isCached
                    ? "var(--status-verified-bg)"
                    : "var(--accent-blue-subtle)",
                  color: isGemini
                    ? "#6366f1"
                    : isCached
                    ? "var(--status-verified-text)"
                    : "var(--accent-blue)",
                  border: `1px solid ${
                    isGemini
                      ? "rgba(99, 102, 241, 0.3)"
                      : isCached
                      ? "var(--status-verified-border)"
                      : "var(--border-subtle)"
                  }`,
                }}
              >
                {isGemini ? (
                  <>
                    <Sparkles size={10} />
                    Gemini Explanation
                  </>
                ) : isCached ? (
                  <>
                    <CheckCircle2 size={10} />
                    Cached Insight
                  </>
                ) : (
                  <>
                    <ShieldCheck size={10} />
                    Rule-Based Grounding
                  </>
                )}
              </span>
            </div>
            <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
              {explanation.summary}
            </p>
          </div>
        </div>

        {/* Expand / Collapse & Refresh Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexShrink: 0 }}>
          <button
            onClick={handleManualRefresh}
            title="Refresh explanation"
            disabled={isLoading}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              padding: "0.25rem",
              display: "flex",
              alignItems: "center",
              borderRadius: "4px",
            }}
          >
            <RotateCw size={13} style={{ animation: isLoading ? "spin 1s linear infinite" : undefined }} />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
              padding: "0.25rem 0.55rem",
              borderRadius: "4px",
              border: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-card)",
              color: "var(--text-secondary)",
              fontSize: "0.72rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.25rem",
            }}
          >
            {isExpanded ? (
              <>
                Less <ChevronUp size={12} />
              </>
            ) : (
              <>
                Explain in depth <ChevronDown size={12} />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Expanded Deep Analysis Body */}
      {isExpanded && (
        <div style={{ padding: "0.85rem 1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {/* Section 1: What you are looking at & What NexusAct found */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div
              style={{
                padding: "0.6rem 0.75rem",
                borderRadius: "6px",
                backgroundColor: "var(--bg-secondary)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.2rem" }}>
                What You Are Looking At
              </div>
              <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                {explanation.what_you_are_looking_at}
              </p>
            </div>

            <div
              style={{
                padding: "0.6rem 0.75rem",
                borderRadius: "6px",
                backgroundColor: "var(--bg-secondary)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--accent-blue)", textTransform: "uppercase", marginBottom: "0.2rem" }}>
                What NexusAct Found
              </div>
              <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--text-primary)", lineHeight: 1.4 }}>
                {explanation.what_nexusact_found}
              </p>
            </div>
          </div>

          {/* Section 2: Why it matters */}
          <div
            style={{
              padding: "0.6rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "rgba(37, 99, 235, 0.05)",
              border: "1px solid var(--border-focus)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.72rem", fontWeight: 700, color: "var(--accent-blue)", textTransform: "uppercase", marginBottom: "0.2rem" }}>
              <Info size={13} /> Why It Matters
            </div>
            <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--text-primary)", lineHeight: 1.4 }}>
              {explanation.why_it_matters}
            </p>
          </div>

          {/* Section 3: Evidence & Relationships */}
          {explanation.evidence_and_relationships && explanation.evidence_and_relationships.length > 0 && (
            <div>
              <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.3rem" }}>
                Connected Evidence & Relationships
              </div>
              <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.76rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {explanation.evidence_and_relationships.map((ev, idx) => (
                  <li key={`ev-${idx}`}>{ev}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Section 4: Confidence & Limitations */}
          <div
            style={{
              padding: "0.5rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "flex-start",
              gap: "0.4rem",
              fontSize: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            <HelpCircle size={14} style={{ marginTop: "1px", flexShrink: 0, color: "var(--text-muted)" }} />
            <div>
              <strong style={{ color: "var(--text-secondary)" }}>Confidence & Limitations: </strong>
              {explanation.confidence_and_limitations}
            </div>
          </div>

          {/* Section 5: Recommended Next Step */}
          <div
            style={{
              padding: "0.55rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "var(--status-verified-bg)",
              border: "1px solid var(--status-verified-border)",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              fontSize: "0.76rem",
              color: "var(--status-verified-text)",
            }}
          >
            <ArrowRight size={14} style={{ flexShrink: 0 }} />
            <div>
              <strong>Recommended Next Step: </strong>
              {explanation.recommended_next_step}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
