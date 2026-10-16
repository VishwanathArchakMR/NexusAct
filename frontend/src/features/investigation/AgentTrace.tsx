import React from "react";
import type { InvestigationStep } from "../../types/investigation";
import { Terminal, CheckCircle2, XCircle, Clock } from "lucide-react";

interface AgentTraceProps {
  steps: InvestigationStep[];
  investigationId?: string;
}

export const AgentTrace: React.FC<AgentTraceProps> = ({ steps, investigationId }) => {
  if (!steps || steps.length === 0) {
    return (
      <div
        style={{
          padding: "1.5rem",
          textAlign: "center",
          color: "var(--text-muted)",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle)",
          fontSize: "0.85rem",
        }}
      >
        <Terminal size={28} color="var(--border-strong)" style={{ marginBottom: "0.5rem" }} />
        <p>No agent tool invocations recorded yet.</p>
        <p style={{ fontSize: "0.78rem", marginTop: "0.25rem" }}>
          Run an investigation to view adaptive MCP tool chaining in real time.
        </p>
      </div>
    );
  }

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
          <Terminal size={16} color="var(--accent-blue)" />
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Agent MCP Tool Execution Trace
          </h3>
        </div>
        {investigationId && (
          <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            {investigationId}
          </span>
        )}
      </div>

      <div style={{ padding: "0.75rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {steps.map((step) => {
          const isSuccess = step.status === "COMPLETED";

          return (
            <div
              key={step.step_number}
              style={{
                border: "1px solid var(--border-subtle)",
                borderRadius: "6px",
                padding: "0.75rem",
                backgroundColor: "var(--bg-card)",
                transition: "border-color 0.15s ease",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.35rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      fontWeight: 700,
                      backgroundColor: "var(--bg-muted)",
                      color: "var(--text-secondary)",
                      padding: "0.1rem 0.4rem",
                      borderRadius: "4px",
                    }}
                  >
                    Step {step.step_number}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      color: "var(--accent-blue)",
                    }}
                  >
                    {step.tool_name}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.25rem",
                      fontSize: "0.7rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    <Clock size={12} />
                    {step.execution_time_ms}ms
                  </span>
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.2rem",
                      fontSize: "0.7rem",
                      fontWeight: 600,
                      color: isSuccess ? "var(--status-verified-text)" : "var(--status-contradicted-text)",
                    }}
                  >
                    {isSuccess ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                    {step.status}
                  </span>
                </div>
              </div>

              {step.purpose && (
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>
                  <strong>Intent:</strong> {step.purpose}
                </p>
              )}

              {step.result_summary && (
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-primary)",
                    backgroundColor: "var(--bg-muted)",
                    padding: "0.45rem 0.65rem",
                    borderRadius: "4px",
                    borderLeft: "3px solid var(--accent-blue)",
                  }}
                >
                  {step.result_summary}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
