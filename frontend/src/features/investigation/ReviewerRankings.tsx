import React from "react";
import type { WhoKnowsOutput } from "../../types/investigation";
import { Users, AlertCircle } from "lucide-react";


interface ReviewerRankingsProps {
  data: WhoKnowsOutput | null;
}

export const ReviewerRankings: React.FC<ReviewerRankingsProps> = ({ data }) => {
  if (!data || data.candidates.length === 0) {
    return (
      <div
        style={{
          padding: "1.5rem",
          textAlign: "center",
          color: "var(--text-muted)",
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          fontSize: "0.85rem",
        }}
      >
        <Users size={28} color="var(--border-strong)" style={{ marginBottom: "0.5rem" }} />
        <p>No reviewer recommendations available.</p>
        <p style={{ fontSize: "0.78rem", marginTop: "0.25rem" }}>
          Run who_knows or an investigation to identify engineers with relevant commit history.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: "#ffffff",
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
          <Users size={16} color="var(--accent-blue)" />
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Recommended Reviewers ({data.candidates.length})
          </h3>
        </div>
        <span
          style={{
            fontSize: "0.7rem",
            backgroundColor: "var(--status-verified-bg)",
            color: "var(--status-verified-text)",
            border: "1px solid var(--status-verified-border)",
            padding: "0.15rem 0.45rem",
            borderRadius: "4px",
            fontWeight: 600,
          }}
        >
          {data.evidence_status}
        </span>
      </div>

      {/* Formula Explainer */}
      <div
        style={{
          padding: "0.5rem 1rem",
          fontSize: "0.72rem",
          color: "var(--text-muted)",
          backgroundColor: "#fafafa",
          borderBottom: "1px solid var(--border-subtle)",
          fontFamily: "var(--font-mono)",
        }}
      >
        Score Formula: {data.scoring_formula}
      </div>

      <div style={{ padding: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {data.candidates.map((cand) => (
          <div
            key={cand.person_id}
            style={{
              border: "1px solid var(--border-subtle)",
              borderRadius: "6px",
              padding: "0.75rem",
              backgroundColor: "#ffffff",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "0.4rem",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <span
                    style={{
                      width: "18px",
                      height: "18px",
                      borderRadius: "50%",
                      backgroundColor: "var(--accent-blue-subtle)",
                      color: "var(--accent-blue)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "0.7rem",
                      fontWeight: 700,
                    }}
                  >
                    #{cand.rank}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-primary)" }}>
                    {cand.name}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "1.5rem" }}>
                  {cand.email}
                </div>
              </div>

              <div style={{ textAlign: "right" }}>
                <span
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    color: "var(--accent-blue)",
                    backgroundColor: "var(--accent-blue-subtle)",
                    padding: "0.15rem 0.5rem",
                    borderRadius: "4px",
                  }}
                >
                  {(cand.composite_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <p style={{ fontSize: "0.76rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
              {cand.rationale}
            </p>

            {/* Score Breakdown Bar */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "0.4rem",
                fontSize: "0.7rem",
                color: "var(--text-muted)",
                backgroundColor: "var(--bg-muted)",
                padding: "0.45rem",
                borderRadius: "4px",
              }}
            >
              <div>
                <span style={{ display: "block", color: "var(--text-secondary)", fontWeight: 600 }}>Files</span>
                {cand.breakdown.files_touched_count} touched ({(cand.breakdown.files_touched_score * 100).toFixed(0)}%)
              </div>
              <div>
                <span style={{ display: "block", color: "var(--text-secondary)", fontWeight: 600 }}>Recency</span>
                {cand.breakdown.days_since_last_touch}d ago ({(cand.breakdown.recency_score * 100).toFixed(0)}%)
              </div>
              <div>
                <span style={{ display: "block", color: "var(--text-secondary)", fontWeight: 600 }}>Commits</span>
                {cand.breakdown.commits_count} commits
              </div>
              <div>
                <span style={{ display: "block", color: "var(--text-secondary)", fontWeight: 600 }}>Reviews</span>
                {cand.breakdown.has_review_history ? "Recorded" : "None"}
              </div>
            </div>

            {/* Missing Evidence Callouts */}
            {cand.missing_evidence && cand.missing_evidence.length > 0 && (
              <div
                style={{
                  marginTop: "0.4rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                  fontSize: "0.7rem",
                  color: "var(--status-unknown-text)",
                }}
              >
                <AlertCircle size={12} />
                <span>Missing: {cand.missing_evidence.join(", ")}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
