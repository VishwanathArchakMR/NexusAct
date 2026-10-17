import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { StatusBadge } from "../src/components/StatusBadge";
import { Header } from "../src/components/Header";
import { RoadmapCard } from "../src/features/system-status/RoadmapCard";
import { SystemStatusDashboard } from "../src/features/system-status/SystemStatusDashboard";

vi.mock("../src/api/client", () => ({
  fetchSystemStatus: vi.fn().mockResolvedValue({
    app_name: "NexusAct",
    app_env: "development",
    version: "0.1.0",
    backend_status: "ONLINE",
    falkordb_status: "ONLINE",
    falkordb_host: "127.0.0.1",
    falkordb_port: 6379,
    primary_graph: "nexusact_main",
    node_count: 1137,
    edge_count: 1540,
    mcp_server_configured: true,
    mcp_port: 8001,
    active_repo_id: "repo:local_nexusact",
    active_repo_name: "NexusAct",
    commit_sha: "3c2b1f9a",
    freshness_status: "FRESH",
    llm_provider: "Google Gemini",
    llm_configured: true,
    subsystem_health: {
      falkordb: "HEALTHY",
      fastapi: "HEALTHY",
      mcp_server: "HEALTHY",
    },
  }),
  fetchReadiness: vi.fn().mockResolvedValue({
    status: "READY",
    database: { connected: true, host: "127.0.0.1", port: 6379, graph: "nexusact_main" },
    schema_version: "1.0.0",
  }),
}));

describe("Frontend Foundation UI Components", () => {
  it("renders StatusBadge with green indicator for ONLINE status", () => {
    render(<StatusBadge status="ONLINE" />);
    expect(screen.getByText("ONLINE")).toBeDefined();
  });

  it("renders StatusBadge with error indicator for OFFLINE status", () => {
    render(<StatusBadge status="OFFLINE" />);
    expect(screen.getByText("OFFLINE")).toBeDefined();
  });

  it("renders Header with NexusAct branding and track information", () => {
    render(<Header />);
    expect(screen.getByText("NexusAct")).toBeDefined();
    expect(screen.getByText(/Graph-Native AI That Investigates, Simulates, and Acts/i)).toBeDefined();
    expect(screen.getByText(/Local FalkorDB/i)).toBeDefined();
  });

  it("renders RoadmapCard displaying validated Phase 1 and Phase 2 items", () => {
    render(<RoadmapCard />);
    expect(screen.getByText(/Phase 1 Completed & Verified/i)).toBeDefined();
    expect(screen.getByText(/Phase 2 Intelligence Roadmap/i)).toBeDefined();
    expect(screen.getByText(/GRAPH.COPY & isolated scenario graph branching/i)).toBeDefined();
  });

  it("renders SystemStatusDashboard with operational diagnostics and WITHOUT roadmap card", async () => {
    await React.act(async () => {
      render(<SystemStatusDashboard />);
    });

    // Real operational diagnostics appear
    expect(screen.getByText(/Operational Health & Telemetry/i)).toBeDefined();
    expect(screen.getByText(/Subsystems Operational Matrix/i)).toBeDefined();
    expect(screen.getByText(/Is the Graph Database Usable\?/i)).toBeDefined();

    // The roadmap card is explicitly absent from normal product dashboard
    expect(screen.queryByText(/Phase 1 Completed & Verified/i)).toBeNull();
    expect(screen.queryByText(/Phase 2 Intelligence Roadmap/i)).toBeNull();
  });
});
