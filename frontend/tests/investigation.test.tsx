import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { AgentTrace } from "../src/features/investigation/AgentTrace";
import { ReviewerRankings } from "../src/features/investigation/ReviewerRankings";
import { CounterfactualDiff } from "../src/features/investigation/CounterfactualDiff";
import { GraphCanvas } from "../src/features/investigation/GraphCanvas";
import type { WhoKnowsOutput, SimulationResult, InvestigationStep, SubgraphResponse } from "../src/types/investigation";

describe("Phase 2 Investigation UI Components", () => {
  it("renders AgentTrace with recorded MCP tool steps", () => {
    const mockSteps: InvestigationStep[] = [
      {
        step_number: 1,
        tool_name: "nexusact_trace_impact",
        arguments: { module_identifier: "mod:backend.app.graph.client" },
        purpose: "Find upstream reverse dependencies",
        status: "COMPLETED",
        result_summary: "Found 12 impacted upstream modules within 4 hops.",
        execution_time_ms: 45.2,
      },
    ];

    render(<AgentTrace steps={mockSteps} investigationId="inv_test_123" />);
    expect(screen.getByText("Agent MCP Tool Execution Trace")).toBeDefined();
    expect(screen.getByText("nexusact_trace_impact")).toBeDefined();
    expect(screen.getByText("Step 1")).toBeDefined();
    expect(screen.getByText(/Found 12 impacted upstream modules/i)).toBeDefined();
  });

  it("renders ReviewerRankings with transparent scores and missing evidence callout", () => {
    const mockReviewers: WhoKnowsOutput = {
      target_module_id: "mod:backend.app.graph.client",
      investigated_modules: ["mod:backend.app.graph.client"],
      candidates: [
        {
          person_id: "person:dev@example.com",
          name: "Alice Engineer",
          email: "dev@example.com",
          composite_score: 0.88,
          rank: 1,
          breakdown: {
            files_touched_score: 1.0,
            recency_score: 0.9,
            ownership_score: 1.0,
            review_history_score: 0.0,
            files_touched_count: 4,
            commits_count: 5,
            days_since_last_touch: 2,
            has_review_history: false,
          },
          rationale: "Modified 4 relevant files across 5 commits.",
          missing_evidence: ["PR peer review records unavailable in local Git log"],
        },
      ],
      scoring_formula: "composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews",
      evidence_status: "VERIFIED",
    };

    render(<ReviewerRankings data={mockReviewers} />);
    expect(screen.getByText(/Alice Engineer/i)).toBeDefined();
    expect(screen.getByText(/88%/i)).toBeDefined();
    expect(screen.getByText(/PR peer review records unavailable/i)).toBeDefined();
  });

  it("renders CounterfactualDiff with blast radius score and topological disclaimer", () => {
    const mockSim: SimulationResult = {
      scenario_id: "scen_test",
      target_module_id: "mod:backend.app.graph.client",
      target_module_name: "backend.app.graph.client",
      baseline_paths_count: 12,
      baseline_node_count: 35,
      disappeared_paths_count: 12,
      disappeared_paths: [
        {
          dependent_module_id: "mod:caller",
          dependent_module_name: "caller",
          broken_path: ["caller", "backend.app.graph.client"],
          hops: 1,
        },
      ],
      surviving_paths_count: 0,
      surviving_paths: [],
      newly_isolated_modules: ["caller"],
      surviving_modules_count: 34,
      surviving_edges_count: 67,
      blast_radius_score: 0.15,
      is_incomplete: false,
      disclaimer: "Simulation prediction is derived from static dependency topology.",
    };

    render(
      <CounterfactualDiff
        simulation={mockSim}
        activeView="baseline"
        onToggleView={() => {}}
      />
    );

    expect(screen.getAllByText(/Broken Paths/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/15\.0%/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Simulation prediction is derived from static dependency topology/i)).toBeDefined();
  });

  it("renders GraphCanvas with nodes and edges", () => {
    const mockSubgraph: SubgraphResponse = {
      nodes: [
        { id: "mod:a", label: "Module A", type: "Module" },
        { id: "mod:b", label: "Module B", type: "Module" },
      ],
      edges: [
        { id: "mod:a->mod:b", source: "mod:a", target: "mod:b", label: "DEPENDS_ON", evidence_type: "observed" },
      ],
      total_nodes: 2,
      total_edges: 1,
    };

    render(<GraphCanvas data={mockSubgraph} targetNodeId="mod:b" />);
    expect(screen.getByText(/2 Nodes/i)).toBeDefined();
    expect(screen.getByText(/1 Edges/i)).toBeDefined();
  });
});
