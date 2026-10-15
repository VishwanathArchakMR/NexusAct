import React, { useState } from "react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { InvestigationWorkspace } from "../features/investigation/InvestigationWorkspace";
import { SystemStatusDashboard } from "../features/system-status/SystemStatusDashboard";
import { Sparkles, Activity } from "lucide-react";
import "./App.css";

export const App: React.FC = () => {
  const [view, setView] = useState<"investigate" | "system">("investigate");

  return (
    <div className="app-layout" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Header />

      {/* Main Mode Navigation Bar */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderBottom: "1px solid var(--border-subtle)",
          padding: "0.4rem 2rem",
        }}
      >
        <div
          style={{
            maxWidth: "1280px",
            margin: "0 auto",
            display: "flex",
            gap: "0.5rem",
          }}
        >
          <button
            onClick={() => setView("investigate")}
            style={{
              padding: "0.4rem 0.85rem",
              fontSize: "0.8rem",
              fontWeight: 600,
              borderRadius: "6px",
              border: "none",
              backgroundColor: view === "investigate" ? "var(--accent-blue-subtle)" : "transparent",
              color: view === "investigate" ? "var(--accent-blue)" : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Sparkles size={14} />
            Graph Investigation Workspace
          </button>

          <button
            onClick={() => setView("system")}
            style={{
              padding: "0.4rem 0.85rem",
              fontSize: "0.8rem",
              fontWeight: 600,
              borderRadius: "6px",
              border: "none",
              backgroundColor: view === "system" ? "var(--accent-blue-subtle)" : "transparent",
              color: view === "system" ? "var(--accent-blue)" : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Activity size={14} />
            System Telemetry & Database Diagnostics
          </button>
        </div>
      </div>

      <main className="app-content" style={{ flex: 1 }}>
        {view === "investigate" ? <InvestigationWorkspace /> : <SystemStatusDashboard />}
      </main>

      <Footer />
    </div>
  );
};

export default App;
