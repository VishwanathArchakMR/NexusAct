import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { StatusBadge } from "../src/components/StatusBadge";
import { Header } from "../src/components/Header";
import { RoadmapCard } from "../src/features/system-status/RoadmapCard";

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
});
