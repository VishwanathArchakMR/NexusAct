import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { PanelExplanation } from "../src/features/investigation/PanelExplanation";
import * as client from "../src/api/client";
import type { PanelExplanationResponse } from "../src/types/investigation";

vi.mock("../src/api/client", () => ({
  fetchPanelExplanation: vi.fn(),
}));

describe("Phase 17 — PanelExplanation and Graph Intelligence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders explanation summary, Gemini badge, and deep breakdown upon expansion", async () => {
    const mockResponse: PanelExplanationResponse = {
      summary: "Dependency relationships form a multi-cluster acyclic structure with 369 imports.",
      what_you_are_looking_at: "A multi-layered interactive graph canvas visualizing module and file nodes.",
      what_nexusact_found: "120 modules connected by 369 static AST import relationships.",
      why_it_matters: "Circular dependencies are absent, simplifying refactoring blast radius.",
      evidence_and_relationships: [
        "120 files parsed across frontend and backend",
        "369 verified DEPENDS_ON edges extracted from AST",
      ],
      confidence_and_limitations: "High confidence based on AST extraction.",
      recommended_next_step: "Run blast radius simulation before modifying core parser.",
      provider_status: "gemini",
      cache_key: "cache:inv_123:graph",
      model_name: "gemini-2.5-pro",
    };

    (client.fetchPanelExplanation as any).mockResolvedValue(mockResponse);

    await React.act(async () => {
      render(
        <PanelExplanation
          panelId="graph"
          investigationId="inv_test_123"
          repoId="repo:local_nexusact"
          commitSha="2e06965"
          dataSummary={{ total_nodes: 120, total_edges: 369 }}
          question="Investigate structure"
        />
      );
    });

    // Check summary and badge
    expect(screen.getByText(/Dependency relationships form a multi-cluster/i)).toBeDefined();
    expect(screen.getByText("Gemini Explanation")).toBeDefined();

    // Expand details
    const expandBtn = screen.getByText(/Explain in depth/i);
    await React.act(async () => {
      fireEvent.click(expandBtn);
    });

    // Check detailed fields
    expect(screen.getByText(/A multi-layered interactive graph canvas visualizing/i)).toBeDefined();
    expect(screen.getByText(/120 modules connected by 369 static AST import relationships/i)).toBeDefined();
    expect(screen.getByText(/120 files parsed across frontend and backend/i)).toBeDefined();
    expect(screen.getByText(/Run blast radius simulation before modifying core parser/i)).toBeDefined();
  });

  it("gracefully returns null when explanation encounters an error", async () => {
    (client.fetchPanelExplanation as any).mockRejectedValue(new Error("Network disconnect"));

    const { container } = await React.act(async () => {
      return render(
        <PanelExplanation
          panelId="simulation"
          investigationId="inv_test_err"
          repoId="repo:local_nexusact"
          dataSummary={{ blast_radius: 5 }}
          question="Analyze blast radius"
        />
      );
    });

    // When an error occurs and no explanation is loaded, it gracefully renders nothing
    expect(container.firstChild).toBeNull();
  });
});
