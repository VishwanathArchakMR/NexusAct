import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { App } from "../src/app/App";
import { InvestigationCenter } from "../src/features/investigation/InvestigationCenter";

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
  fetchPanelExplanation: vi.fn().mockResolvedValue({
    explanation_id: "exp_test",
    panel_id: "graph",
    headline: "Grounded Graph Explanation",
    summary: "Mock explanation for testing.",
    grounded_facts: ["Fact 1"],
    inferences: ["Inference 1"],
    confidence_rating: "HIGH",
    evidence_status: "VERIFIED",
    provider: "gemini-fallback",
    cached: false,
  }),
}));

describe("Phase 18 Investigation Center and Navigation Quality Gates", () => {
  it("renders primary navigation with Software Graph first and default opening workspace", async () => {
    await React.act(async () => {
      render(<App />);
    });
    // Check navigation buttons
    const softwareTab = screen.getByRole("button", { name: /Software Graph/i });
    const investigationTab = screen.getByRole("button", { name: /Investigation Center/i });
    const diagnosticsTab = screen.getByRole("button", { name: /Diagnostics/i });

    expect(softwareTab).toBeDefined();
    expect(investigationTab).toBeDefined();
    expect(diagnosticsTab).toBeDefined();

    // Default view is Software Graph workspace
    expect(screen.getByText(/Dynamic Graph Intelligence Investigation/i)).toBeDefined();

    // Switch to Investigation Center
    await React.act(async () => {
      fireEvent.click(investigationTab);
    });
    expect(screen.getByRole("heading", { name: "Investigation Center" })).toBeDefined();
    expect(screen.getByRole("heading", { name: /Codebase Walkthrough/i })).toBeDefined();
    expect(screen.getByRole("heading", { name: /Security Vulnerability Triage/i })).toBeDefined();
    expect(screen.getByRole("heading", { name: /Fraud Investigation/i })).toBeDefined();
  });

  it("renders the 3 operational workflow entry points and launches a workflow into Software Graph", async () => {
    const handleLaunch = vi.fn();
    await React.act(async () => {
      render(
        <InvestigationCenter
          selectedRepoId="repo:local_nexusact"
          onSelectRepoId={vi.fn()}
          onLaunchWorkflow={handleLaunch}
        />
      );
    });

    const walkthroughBtn = screen.getByRole("button", { name: /Launch Codebase Walkthrough/i });
    const securityBtn = screen.getByRole("button", { name: /Launch Security Triage/i });
    const fraudBtn = screen.getByRole("button", { name: /Launch Fraud Investigation/i });

    expect(walkthroughBtn).toBeDefined();
    expect(securityBtn).toBeDefined();
    expect(fraudBtn).toBeDefined();

    await React.act(async () => {
      fireEvent.click(walkthroughBtn);
    });
    expect(handleLaunch).toHaveBeenCalledWith("codebase_walkthrough", "graph");

    await React.act(async () => {
      fireEvent.click(securityBtn);
    });
    expect(handleLaunch).toHaveBeenCalledWith("security_triage", "security");

    await React.act(async () => {
      fireEvent.click(fraudBtn);
    });
    expect(handleLaunch).toHaveBeenCalledWith("fraud_demo", "fraud");
  });

  it("renders recent FalkorDB graph investigations and allows opening an investigation", async () => {
    const handleLaunch = vi.fn();
    await React.act(async () => {
      render(
        <InvestigationCenter
          selectedRepoId="repo:local_nexusact"
          onSelectRepoId={vi.fn()}
          onLaunchWorkflow={handleLaunch}
        />
      );
    });

    expect(screen.getByText(/Recent Graph Investigations/i)).toBeDefined();
    expect(screen.getByText(/Explore citation relationships between neural network research works\./i)).toBeDefined();

    const openBtn = screen.getByRole("button", { name: /Open/i });
    expect(openBtn).toBeDefined();

    await React.act(async () => {
      fireEvent.click(openBtn);
    });
    expect(handleLaunch).toHaveBeenCalled();
  });
});
