import React from "react";
import { GitGraph, ShieldCheck, Terminal } from "lucide-react";

export const Header: React.FC = () => {
  return (
    <header
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        backgroundColor: "var(--bg-secondary)",
        padding: "1rem 2rem",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div
            style={{
              width: "2.75rem",
              height: "2.75rem",
              borderRadius: "0.5rem",
              background: "linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              boxShadow: "0 4px 12px rgba(59, 130, 246, 0.25)",
            }}
          >
            <GitGraph size={24} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h1 style={{ fontSize: "1.35rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
                NexusAct
              </h1>
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "0.15rem 0.45rem",
                  borderRadius: "4px",
                  backgroundColor: "rgba(59, 130, 246, 0.15)",
                  color: "var(--accent-blue)",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  fontWeight: 600,
                }}
              >
                GAF Architecture
              </span>
            </div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
              Graph-Native AI That Investigates, Simulates, and Acts
            </p>

          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              padding: "0.35rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <ShieldCheck size={15} color="#34d399" />
            Local FalkorDB v4.4.1
          </span>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              padding: "0.35rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <Terminal size={15} color="#60a5fa" />
            FastAPI + MCP
          </span>
        </div>
      </div>
    </header>
  );
};
