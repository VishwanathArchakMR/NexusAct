import React, { useEffect, useState, useCallback } from "react";
import {
  Server,
  Database,
  Cpu,
  RefreshCw,
  Layers,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { fetchReadiness, fetchSystemStatus } from "../../api/client";
import type { ReadinessData, SystemStatusData } from "../../types/system";
import { DiagnosticCard } from "./DiagnosticCard";
import { RoadmapCard } from "./RoadmapCard";

export const SystemStatusDashboard: React.FC = () => {
  const [statusData, setStatusData] = useState<SystemStatusData | null>(null);
  const [readinessData, setReadinessData] = useState<ReadinessData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sysStatus, readiness] = await Promise.all([
        fetchSystemStatus(),
        fetchReadiness(),
      ]);
      setStatusData(sysStatus);
      setReadinessData(readiness);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err: any) {
      console.error("Telemetry fetch error:", err);
      setError(err?.message || "Failed to reach NexusAct backend API");
      setLastRefreshed(new Date().toLocaleTimeString());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const execute = async () => {
      if (mounted) {
        await loadData();
      }
    };
    void execute();
    const interval = setInterval(loadData, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [loadData]);

  const backendState = error ? "OFFLINE" : statusData ? statusData.backend_status : "LOADING";
  const falkorState = error
    ? "UNAVAILABLE"
    : readinessData
    ? readinessData.database.connected
      ? "HEALTHY"
      : "DEGRADED"
    : "LOADING";

  return (
    <main
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "2rem",
        display: "flex",
        flexDirection: "column",
        gap: "2rem",
      }}
    >
      {/* Title & Action Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h2 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Foundation Health & Connectivity
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
            Real-time telemetry from FastAPI backend and persistent FalkorDB graph engine.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          {lastRefreshed && (
            <span
              style={{
                fontSize: "0.8rem",
                color: "var(--text-muted)",
                display: "flex",
                alignItems: "center",
                gap: "0.35rem",
              }}
            >
              <Clock size={13} /> Updated at {lastRefreshed}
            </span>
          )}
          <button
            onClick={loadData}
            disabled={loading}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.5rem 1rem",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "0.5rem",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
              fontWeight: 500,
              transition: "all 0.15s ease",
            }}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            {loading ? "Checking..." : "Refresh Status"}
          </button>
        </div>
      </div>

      {/* Error Banner if Backend is down */}
      {error && (
        <div
          style={{
            backgroundColor: "var(--status-error-bg)",
            border: "1px solid var(--status-error-border)",
            borderRadius: "0.75rem",
            padding: "1rem 1.25rem",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color: "var(--status-error-text)",
          }}
        >
          <AlertTriangle size={20} />
          <div>
            <span style={{ fontWeight: 600 }}>Backend Connectivity Failure: </span>
            <span>{error}</span>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
              Make sure the FastAPI backend is running via <code>python -m uvicorn backend.app.main:app</code> on port 8000.
            </p>
          </div>
        </div>
      )}

      {/* Diagnostics Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "1.25rem",
        }}
      >
        <DiagnosticCard
          title="Backend API"
          subtitle="FastAPI Microservice"
          status={backendState}
          icon={Server}
          iconColor="#3b82f6"
          details={[
            { label: "Environment", value: statusData?.app_env || "local" },
            { label: "Version", value: statusData?.version || "0.1.0" },
            { label: "Endpoint", value: "127.0.0.1:8000" },
          ]}
        />

        <DiagnosticCard
          title="FalkorDB Engine"
          subtitle="Primary Graph Database"
          status={falkorState}
          icon={Database}
          iconColor="#10b981"
          details={[
            { label: "Host / Port", value: `${statusData?.falkordb_host || "127.0.0.1"}:${statusData?.falkordb_port || 6379}` },
            { label: "Primary Graph", value: statusData?.primary_graph || "nexusact_main" },
            { label: "Schema Version", value: readinessData?.schema_version || "1.0.0" },
          ]}
        />

        <DiagnosticCard
          title="MCP Diagnostics"
          subtitle="Restricted Tool Server"
          status={statusData?.mcp_server_configured ? "ONLINE" : "OFFLINE"}
          icon={Cpu}
          iconColor="#8b5cf6"
          details={[
            { label: "Registered Tools", value: "nexusact_diagnose_graph" },
            { label: "Classification", value: "Read-only" },
            { label: "MCP Transport", value: "Stdio / RPC" },
          ]}
        />

        <DiagnosticCard
          title="Graph Topology"
          subtitle="Telemetry & Entities"
          status={readinessData?.database.connected ? "HEALTHY" : "DEGRADED"}
          icon={Layers}
          iconColor="#06b6d4"
          details={[
            { label: "Total Nodes", value: statusData?.node_count ?? 0 },
            { label: "Total Edges", value: statusData?.edge_count ?? 0 },
            { label: "Isolation Engine", value: "GRAPH.COPY" },
          ]}
        />
      </div>

      {/* Architecture and Roadmap */}
      <RoadmapCard />
    </main>
  );
};
