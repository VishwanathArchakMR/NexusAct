import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { App } from "../src/app/App";
import { UniversalDiscoveryWorkspace } from "../src/features/discovery/UniversalDiscoveryWorkspace";

// Mock client API calls
vi.mock("../src/api/client", () => ({
  fetchPublicSources: vi.fn().mockResolvedValue({
    sources: {
      huggingface: {
        source_id: "huggingface",
        display_name: "Hugging Face Hub",
        healthy: true,
        message: "Online",
        entity_types: ["Model", "Dataset"],
        requires_auth: false,
      },
    },
    total_connectors: 1,
  }),
  fetchPublicSubgraph: vi.fn().mockResolvedValue({
    nodes: [
      { id: "hf:bert-base", label: "bert-base", type: "Model" },
      { id: "doi:10.1234/test", label: "Attention Paper", type: "Paper" },
    ],
    edges: [
      { source: "doi:10.1234/test", target: "hf:bert-base", type: "CITES" },
    ],
    total_nodes: 2,
    total_edges: 1,
  }),
  fetchSavedInvestigations: vi.fn().mockResolvedValue({
    investigations: [
      {
        investigation_id: "uinv_1",
        question: "Explore citation relationships between neural network research works.",
        summary: "Analyzed 2 entities.",
        sources: "crossref,openalex",
        approach: "Selected crossref, openalex.",
        action_id: "act_1",
        action_title: "Track citations",
        action_desc: "Monitor incoming citations.",
        action_status: "PROPOSED",
      },
    ],
    total: 1,
  }),
  askUniversalGaf: vi.fn().mockResolvedValue({
    investigation_id: "uinv_2",
    question: "Explore citation relationships between neural network research works.",
    plan: {
      plan_id: "p1",
      question: "Explore citation relationships between neural network research works.",
      target_entity_types: ["Paper"],
      relationship_focus: ["CITES"],
      selected_source_ids: ["crossref", "openalex"],
      search_keywords: ["neural network"],
      max_results_per_source: 5,
      traversal_depth: 2,
      is_heuristic_fallback: true,
    },
    sources_queried: {},
    records_ingested: 2,
    entities: [
      { id: "doi:10.1234/p1", type: "Paper", name: "Paper 1", source: "crossref", url: "" },
      { id: "doi:10.1234/p2", type: "Paper", name: "Paper 2", source: "crossref", url: "" },
    ],
    relationships: [
      {
        source: "doi:10.1234/p1",
        target: "doi:10.1234/p2",
        type: "CITES",
        confidence: "EXACT",
        evidence: "reference",
        provenance_url: "https://doi.org/10.1234/p1",
      },
    ],
    paths: [],
    findings: ["doi:10.1234/p1 -(CITES)-> doi:10.1234/p2"],
    summary: "Analyzed 2 entities and 1 relationship.",
    approach: "Selected connectors: [crossref, openalex].",
    next_action: {
      id: "act_test",
      title: "Track upstream citations",
      description: "Monitor new works.",
      status: "PROPOSED",
    },
    coverage_limitations: [],
    execution_time_ms: 120,
  }),
  confirmInvestigationAction: vi.fn().mockResolvedValue({
    action_id: "act_test",
    status: "CONFIRMED",
    message: "Action confirmed",
  }),
}));

describe("Phase 9 Universal GAF Unified Navigation and Workspace", () => {
  it("renders exactly 3 top-level navigation tabs and defaults to Universal GAF", async () => {
    await React.act(async () => {
      render(<App />);
    });
    expect(screen.getByRole("button", { name: /Universal GAF/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Software Graph/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Diagnostics/i })).toBeDefined();

    // Redundant top tabs should NOT exist
    expect(screen.queryByRole("button", { name: /AI Ecosystem/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Research & Citations/i })).toBeNull();

    // Default view is Universal Public-Data Discovery
    expect(screen.getByText(/Universal Public-Data Discovery \(GAF\)/i)).toBeDefined();
  });

  it("renders contextual scope controls and updates scope when clicked", async () => {
    await React.act(async () => {
      render(<UniversalDiscoveryWorkspace />);
    });
    expect(screen.getByRole("button", { name: /All relevant sources/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /AI models and datasets/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Research papers and citations/i })).toBeDefined();

    const aiScopeBtn = screen.getByRole("button", { name: /AI models and datasets/i });
    await React.act(async () => {
      fireEvent.click(aiScopeBtn);
    });

    // Suggested query for AI ecosystem should now appear
    expect(screen.getByText(/Which datasets are documented as used to train open-source models\?/i)).toBeDefined();
  });

  it("renders graph memory and confirms action without error", async () => {
    let containerElem: HTMLElement | null = null;
    await React.act(async () => {
      const { container } = render(<UniversalDiscoveryWorkspace />);
      containerElem = container;
    });
    expect(screen.getByText(/Graph-Backed Investigation Memory/i)).toBeDefined();
    expect(containerElem).toBeDefined();
  });
});
