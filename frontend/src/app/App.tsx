import React, { useState } from "react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { InvestigationWorkspace } from "../features/investigation/InvestigationWorkspace";
import { UniversalDiscoveryWorkspace } from "../features/discovery/UniversalDiscoveryWorkspace";
import { SystemStatusDashboard } from "../features/system-status/SystemStatusDashboard";
import { GitBranch, Globe, Activity } from "lucide-react";
import "./App.css";

export type AppViewMode = "software" | "universal" | "system";

export const App: React.FC = () => {
  const [view, setView] = useState<AppViewMode>("software");
  const [sharedRepoId, setSharedRepoId] = useState<string>("repo:local_nexusact");

  const tabs: Array<{ id: AppViewMode; label: string; icon: React.ReactNode }> = [
    { id: "software", label: "Software Graph", icon: <GitBranch size={14} /> },
    { id: "universal", label: "Agent Investigation (Universal GAF)", icon: <Globe size={14} /> },
    { id: "system", label: "Diagnostics", icon: <Activity size={14} /> },

  ];

  return (
    <div className="app-layout" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Header />

      {/* Main Mode Navigation Bar */}
      <div
        style={{
          backgroundColor: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border-subtle)",
          padding: "0.4rem 2rem",
        }}
      >
        <div
          style={{
            maxWidth: "1400px",
            margin: "0 auto",
            display: "flex",
            gap: "0.5rem",
            flexWrap: "wrap",
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              style={{
                padding: "0.4rem 0.85rem",
                fontSize: "0.8rem",
                fontWeight: 600,
                borderRadius: "6px",
                border: "none",
                backgroundColor: view === tab.id ? "var(--accent-blue-subtle)" : "transparent",
                color: view === tab.id ? "var(--accent-blue)" : "var(--text-secondary)",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <main className="app-content" style={{ flex: 1 }}>
        {view === "software" && (
          <InvestigationWorkspace
            selectedRepoId={sharedRepoId}
            onSelectRepoId={setSharedRepoId}
          />
        )}
        {view === "universal" && (
          <UniversalDiscoveryWorkspace
            selectedRepoId={sharedRepoId}
            onSelectRepoId={setSharedRepoId}
          />
        )}
        {view === "system" && <SystemStatusDashboard />}
      </main>

      <Footer />
    </div>
  );
};

export default App;

