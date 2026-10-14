import React from "react";
import { Database, Server, Cpu } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--border-subtle)",
        backgroundColor: "var(--bg-secondary)",
        padding: "1.5rem 2rem",
        marginTop: "auto",
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
          fontSize: "0.8rem",
          color: "var(--text-muted)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <Database size={14} /> FalkorDB Native Graph
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <Server size={14} /> FastAPI Backend
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <Cpu size={14} /> MCP Server
          </span>
        </div>
        <div>
          <span>NexusAct Foundation v0.1.0 • Hackathon Track: Agents That Act on Connected Data</span>
        </div>
      </div>
    </footer>
  );
};
