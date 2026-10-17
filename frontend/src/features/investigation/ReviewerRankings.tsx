import React from "react";
import type { WhoKnowsOutput, ReviewerResponseItem, ReviewersQueryResponse } from "../../types/investigation";
import { Users, UserCheck, GitCommit, FileCode, Award, Info, RefreshCw, ShieldCheck } from "lucide-react";

interface ReviewerRankingsProps {
  data?: WhoKnowsOutput | null;
  queryResponse?: ReviewersQueryResponse | null;
  isLoading?: boolean;
  onRefresh?: () => void;
  selectedModule?: string;
  onSelectModule?: (moduleId: string) => void;
  availableModules?: string[];
}

export const ReviewerRankings: React.FC<ReviewerRankingsProps> = ({
  data,
  queryResponse,
  isLoading = false,
  onRefresh,
  selectedModule,
  onSelectModule,
  availableModules = [],
}) => {
  // Merge data from either WhoKnowsOutput or ReviewersQueryResponse
  const candidates: Array<ReviewerResponseItem | any> =
    queryResponse?.candidates || data?.candidates || [];
  const totalRepoAuthors = queryResponse?.total_repo_authors ?? (candidates.length > 0 ? candidates.length : 0);
  const hasExplicitReviews = queryResponse?.has_explicit_reviews ?? false;
  const formula =
    queryResponse?.scoring_formula ||
    data?.scoring_formula ||
    "composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews";

  // Separate reviewers with explicit reviews vs code authorship experts
  const explicitReviewers = candidates.filter(
    (c) => c.breakdown?.has_review_history || c.has_review_history
  );
  const authorExperts = candidates;

  if (isLoading) {
    return (
      <div style={emptyCardStyle}>
        <div
          style={{
            width: "24px",
            height: "24px",
            border: "2px solid var(--accent-blue, #2563eb)",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
            marginBottom: "0.5rem",
          }}
        />
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary, #475569)" }}>
          Traversing Git commit log in FalkorDB...
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", width: "100%" }}>
      {/* ── Filter & Refresh Bar ── */}
      <div
        style={{
          padding: "0.6rem 1rem",
          backgroundColor: "var(--bg-card, #ffffff)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle, #e2e8f0)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-primary, #0f172a)" }}>
            Filter by Module:
          </label>
          <select
            value={selectedModule || ""}
            onChange={(e) => onSelectModule && onSelectModule(e.target.value)}
            style={{
              padding: "0.35rem 0.55rem",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #cbd5e1)",
              backgroundColor: "#ffffff",
              fontSize: "0.78rem",
              color: "var(--text-primary, #0f172a)",
              outline: "none",
            }}
          >
            <option value="">Repository-Wide (All Authors)</option>
            {availableModules.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "0.35rem 0.65rem",
              borderRadius: "6px",
              backgroundColor: "var(--bg-muted, #f8fafc)",
              border: "1px solid var(--border-subtle, #cbd5e1)",
              fontSize: "0.75rem",
              cursor: "pointer",
              color: "var(--text-secondary, #475569)",
            }}
          >
            <RefreshCw size={12} />
            <span>Refresh Contributors</span>
          </button>
        )}
      </div>

      {/* ── Empty State ── */}
      {candidates.length === 0 ? (
        <div style={emptyCardStyle}>
          <Users size={32} color="var(--border-strong, #94a3b8)" style={{ marginBottom: "0.5rem" }} />
          <h4 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-primary, #0f172a)", marginBottom: "0.3rem" }}>
            {totalRepoAuthors > 0
              ? `No direct commit touches for '${selectedModule || "selected module"}'`
              : "No Git Commit History in Graph"}
          </h4>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary, #475569)", maxWidth: "480px", lineHeight: 1.4 }}>
            {totalRepoAuthors > 0 ? (
              <>
                The selected module has no commit touch history linked to its specific files. The repository commit log contains <strong>{totalRepoAuthors} recorded author(s)</strong> overall. Switch the module filter to <em>Repository-Wide</em> to inspect top contributors.
              </>
            ) : (
              <>
                This source snapshot does not contain Git commit records in FalkorDB (<code>(:Person)-[:AUTHORED]-&gt;(:Commit)</code>). Ensure the repository was ingested with Git commit history enabled to view author expertise.
              </>
            )}
          </p>
          {totalRepoAuthors > 0 && selectedModule && onSelectModule && (
            <button
              onClick={() => onSelectModule("")}
              style={{
                marginTop: "0.75rem",
                padding: "0.4rem 0.85rem",
                borderRadius: "6px",
                backgroundColor: "var(--accent-blue, #2563eb)",
                color: "#ffffff",
                border: "none",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              View Repository-Wide Contributors
            </button>
          )}
        </div>
      ) : (
        <div style={{ backgroundColor: "var(--bg-card, #ffffff)", borderRadius: "8px", border: "1px solid var(--border-subtle, #e2e8f0)", overflow: "hidden" }}>
          {/* Header */}
          <div
            style={{
              padding: "0.75rem 1rem",
              backgroundColor: "var(--bg-muted, #f8fafc)",
              borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.5rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Users size={16} color="var(--accent-blue, #2563eb)" />
              <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary, #0f172a)" }}>
                Contributor & Reviewer Intelligence ({candidates.length} ranked)
              </h3>
            </div>
            <span
              style={{
                fontSize: "0.7rem",
                backgroundColor: hasExplicitReviews ? "#dcfce7" : "#eff6ff",
                color: hasExplicitReviews ? "#166534" : "#1e40af",
                border: `1px solid ${hasExplicitReviews ? "#bbf7d0" : "#bfdbfe"}`,
                padding: "0.15rem 0.5rem",
                borderRadius: "4px",
                fontWeight: 600,
              }}
            >
              {hasExplicitReviews ? "Explicit Peer Reviews Observed" : "Commit Touch Provenance"}
            </span>
          </div>

          {/* Formula explainer */}
          <div
            style={{
              padding: "0.45rem 1rem",
              fontSize: "0.7rem",
              color: "var(--text-muted, #64748b)",
              backgroundColor: "#fafafa",
              borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
              fontFamily: "var(--font-mono, monospace)",
            }}
          >
            Ranking Formula: {formula}
          </div>

          {/* ── Section 1: Reviewers ── */}
          <div style={{ padding: "0.85rem 1rem", borderBottom: "1px solid var(--border-subtle, #e2e8f0)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.6rem" }}>
              <UserCheck size={16} color="#16a34a" />
              <h4 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
                Recommended Code Reviewers
              </h4>
            </div>

            {hasExplicitReviews && explicitReviewers.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {explicitReviewers.map((rev) => (
                  <div key={rev.person_id} style={reviewerCardStyle}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <ShieldCheck size={15} color="#16a34a" />
                      <span style={{ fontWeight: 600, fontSize: "0.8rem", color: "var(--text-primary, #0f172a)" }}>
                        {rev.name}
                      </span>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted, #64748b)" }}>{rev.email}</span>
                    </div>
                    <span style={scoreBadgeStyle}>Score: {(rev.composite_score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "0.6rem 0.75rem",
                  borderRadius: "6px",
                  backgroundColor: "#f8fafc",
                  border: "1px solid var(--border-subtle, #e2e8f0)",
                  fontSize: "0.76rem",
                  color: "var(--text-secondary, #475569)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <Info size={14} color="var(--accent-blue, #2563eb)" />
                <span>
                  <strong>Author-based recommendations:</strong> Direct peer review approvals (<code>REVIEWS</code> edges) are unrecorded; candidates are recommended from code authorship touch history below.
                </span>
              </div>
            )}
          </div>

          {/* ── Section 2: Authors & Expertise ── */}
          <div style={{ padding: "0.85rem 1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.6rem" }}>
              <Award size={16} color="var(--accent-blue, #2563eb)" />
              <h4 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
                Code Authors & Domain Expertise
              </h4>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
              {authorExperts.map((cand, idx) => {
                const commits = cand.commits_count ?? cand.breakdown?.commits_count ?? 0;
                const files = cand.files_touched_count ?? cand.breakdown?.files_touched_count ?? 0;
                const score = cand.composite_score ?? 0;

                return (
                  <div
                    key={cand.person_id || idx}
                    style={{
                      border: "1px solid var(--border-subtle, #e2e8f0)",
                      borderRadius: "6px",
                      padding: "0.65rem 0.85rem",
                      backgroundColor: idx === 0 ? "rgba(37, 99, 235, 0.03)" : "#ffffff",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          style={{
                            width: "20px",
                            height: "20px",
                            borderRadius: "50%",
                            backgroundColor: idx === 0 ? "var(--accent-blue, #2563eb)" : "var(--bg-muted, #f1f5f9)",
                            color: idx === 0 ? "#ffffff" : "var(--text-secondary, #475569)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.7rem",
                            fontWeight: 700,
                          }}
                        >
                          {cand.rank || idx + 1}
                        </span>
                        <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-primary, #0f172a)" }}>
                          {cand.name}
                        </span>
                        {cand.is_lead && (
                          <span style={leadBadgeStyle}>Lead Author</span>
                        )}
                        {cand.email && (
                          <span style={{ fontSize: "0.72rem", color: "var(--text-muted, #64748b)" }}>
                            ({cand.email})
                          </span>
                        )}
                      </div>

                      <span style={scoreBadgeStyle}>
                        {(score * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.74rem", color: "var(--text-secondary, #475569)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                        <GitCommit size={13} color="var(--accent-blue, #2563eb)" />
                        <span><strong>{commits}</strong> commit{commits !== 1 ? "s" : ""}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                        <FileCode size={13} color="var(--accent-blue, #2563eb)" />
                        <span><strong>{files}</strong> file{files !== 1 ? "s" : ""} touched</span>
                      </div>
                    </div>

                    {cand.rationale && (
                      <div style={{ marginTop: "0.35rem", fontSize: "0.72rem", color: "var(--text-muted, #64748b)" }}>
                        {cand.rationale}
                      </div>
                    )}

                    {cand.missing_evidence && cand.missing_evidence.length > 0 && (
                      <div style={{ marginTop: "0.25rem", fontSize: "0.7rem", color: "var(--text-muted, #64748b)" }}>
                        {cand.missing_evidence.join("; ")}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const emptyCardStyle: React.CSSProperties = {
  padding: "2rem 1.5rem",
  textAlign: "center",
  backgroundColor: "var(--bg-card, #ffffff)",
  borderRadius: "8px",
  border: "1px solid var(--border-subtle, #e2e8f0)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
};

const reviewerCardStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0.5rem 0.75rem",
  borderRadius: "6px",
  backgroundColor: "#f0fdf4",
  border: "1px solid #dcfce7",
};

const scoreBadgeStyle: React.CSSProperties = {
  fontSize: "0.72rem",
  fontWeight: 700,
  padding: "0.15rem 0.45rem",
  borderRadius: "4px",
  backgroundColor: "var(--accent-blue-subtle, #eff6ff)",
  color: "var(--accent-blue, #2563eb)",
  border: "1px solid rgba(37, 99, 235, 0.2)",
};

const leadBadgeStyle: React.CSSProperties = {
  fontSize: "0.68rem",
  fontWeight: 700,
  padding: "0.1rem 0.35rem",
  borderRadius: "4px",
  backgroundColor: "#fef3c7",
  color: "#b45309",
  border: "1px solid #fde68a",
};
