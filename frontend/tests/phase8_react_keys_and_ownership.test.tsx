import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { GraphCanvas } from "../src/features/investigation/GraphCanvas";
import type { SubgraphResponse } from "../src/types/investigation";

describe("Phase 8 UI Key Integrity and Stale Ownership", () => {
  it("GraphCanvas deduplicates duplicate node IDs without throwing duplicate key errors", () => {
    // Intentionally pass duplicated node IDs to test UI key deduplication resilience
    const mockSubgraphWithDuplicates: SubgraphResponse = {
      nodes: [
        { id: "openalex:10.3390/app14219690", label: "Paper 1", type: "Paper" },
        { id: "openalex:10.3390/app14219690", label: "Paper 1 (Duplicate Record)", type: "Paper" },
        { id: "hf:bert-base", label: "BERT Model", type: "Model" },
      ],
      edges: [
        {
          id: "edge-1",
          source: "openalex:10.3390/app14219690",
          target: "hf:bert-base",
          label: "CITES",
          evidence_type: "observed",
        },
        {
          id: "edge-1-dup",
          source: "openalex:10.3390/app14219690",
          target: "hf:bert-base",
          label: "CITES",
          evidence_type: "observed",
        },
      ],
      total_nodes: 3,
      total_edges: 2,
    };

    const consoleErrorSpy = vi.spyOn(console, "error");

    render(
      <GraphCanvas
        data={mockSubgraphWithDuplicates}
        targetNodeId="hf:bert-base"
      />
    );

    // Should render the canvas with deduplicated nodes
    expect(screen.getByText(/Nodes/i)).toBeDefined();
    expect(screen.getByText(/Edges/i)).toBeDefined();

    // Verify React did not log a duplicate key warning
    const duplicateKeyCalls = consoleErrorSpy.mock.calls.filter((call) =>
      call.some((arg) => typeof arg === "string" && arg.includes("Encountered two children with the same key"))
    );
    expect(duplicateKeyCalls.length).toBe(0);

    consoleErrorSpy.mockRestore();
  });

  it("GraphCanvas renders empty state cleanly when zero nodes exist", () => {
    const emptySubgraph: SubgraphResponse = {
      nodes: [],
      edges: [],
      total_nodes: 0,
      total_edges: 0,
    };

    render(<GraphCanvas data={emptySubgraph} />);
    expect(screen.getByText(/No graph nodes selected/i)).toBeDefined();
    expect(screen.getByText(/Select a module or run an investigation to render the live dependency graph/i)).toBeDefined();
  });
});
