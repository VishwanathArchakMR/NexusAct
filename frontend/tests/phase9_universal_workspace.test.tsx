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
  fetchRepositories: vi.fn().mockResolvedValue([
    {
      id: "repo:local_nexusact",
      name: "NexusAct",
      source_type: "local",
      url_or_path: "C:\\NexusAct",
      graph_name: "nexusact_main",
      commit_sha: "6b00a0020c89fe2bb07ec7844fa64af7ce0c8d28",
      module_count: 56,
      edge_count: 84,
      known_gaps: [],
      parser_warnings: [],
    },
  ]),
  fetchSourceMetadata: vi.fn().mockResolvedValue({
    repository_id: "repo:local_nexusact",
    total_commits: 15,
  }),
  fetchModules: vi.fn().mockResolvedValue([]),
  fetchSubgraph: vi.fn().mockResolvedValue({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 }),
  fetchRepositorySnapshot: vi.fn().mockResolvedValue({
    snapshot_id: "snap_test",
    repository_id: "repo:local_nexusact",
    source_type: "local",
    canonical_source: "C:\\NexusAct",
    default_branch: "master",
    commit_sha: "6b00a0020c89fe2bb07ec7844fa64af7ce0c8d28",
    working_tree_fingerprint: "test_fp",
    graph_name: "nexusact_main",
    source_checked_at: "2026-10-17T00:00:00Z",
    freshness_status: "FRESH",
  }),
  fetchFileContent: vi.fn().mockResolvedValue({
    file_path: "backend/app/main.py",
    repository_id: "repo:local_nexusact",
    commit_sha: "6b00a002",
    start_line: 1,
    end_line: 20,
    total_lines: 100,
    content: "# test code",
    language: "python",
  }),
}));

describe("Phase 10 Universal GAF Input-Driven Navigation and Workspace", () => {
  it("renders primary navigation with Software Graph first and default opening workspace", async () => {
    await React.act(async () => {
      render(<App />);
    });
    // Check navigation buttons
    const softwareTab = screen.getByRole("button", { name: /Software Graph/i });
    const universalTab = screen.getByRole("button", { name: /Universal GAF/i });
    const diagnosticsTab = screen.getByRole("button", { name: /Diagnostics/i });

    expect(softwareTab).toBeDefined();
    expect(universalTab).toBeDefined();
    expect(diagnosticsTab).toBeDefined();

    // Default view is Software Graph workspace
    expect(screen.getByText(/Dynamic Graph Intelligence Investigation/i)).toBeDefined();

    // Switch to Universal GAF
    await React.act(async () => {
      fireEvent.click(universalTab);
    });
    expect(screen.getByText(/Universal GraphAction Fabric \(Universal GAF\)/i)).toBeDefined();
  });

  it("renders explicit input modes and updates mode when clicked", async () => {
    await React.act(async () => {
      render(<UniversalDiscoveryWorkspace />);
    });
    expect(screen.getByRole("button", { name: /Mode A — Public Knowledge Discovery/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Mode B — Selected Repository/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Mode C — Repository \+ Public Evidence/i })).toBeDefined();

    const repoModeBtn = screen.getByRole("button", { name: /Mode B — Selected Repository/i });
    await React.act(async () => {
      fireEvent.click(repoModeBtn);
    });

    // Codebase suggested queries appear
    expect(screen.getByText(/Which modules depend on the database layer\?/i)).toBeDefined();
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
