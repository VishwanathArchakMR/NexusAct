import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { GraphCanvas } from "../src/features/investigation/GraphCanvas";
import { FraudInvestigationPanel } from "../src/features/investigation/FraudInvestigationPanel";
import { InvestigationWorkspace } from "../src/features/investigation/InvestigationWorkspace";
import type { SubgraphResponse, FinancialDatasetMetadata } from "../src/types/investigation";

const { mockDataset } = vi.hoisted(() => {
  const mockDataset: FinancialDatasetMetadata = {
    dataset_id: "ds_benchmark_test",
    dataset_name: "Test AML Benchmark",
    graph_name: "fin_benchmark_test",
    source_type: "sample_benchmark",
    record_count: 5,
    account_count: 5,
    transaction_count: 5,
    imported_at: "2026-03-01T12:00:00Z",
    is_anonymized: true,
    has_ground_truth_labels: true,
    provenance_note: "Synthetic AML benchmark dataset",
    data_limitations: ["Anonymized benchmark sample"],
  };
  return { mockDataset };
});

vi.mock("../src/api/client", () => ({
  fetchFinancialDatasets: vi.fn().mockResolvedValue([mockDataset]),
  fetchActiveFinancialDataset: vi.fn().mockResolvedValue(mockDataset),
  activateFinancialDataset: vi.fn(),
  previewFinancialDataset: vi.fn(),
  ingestFinancialDataset: vi.fn(),
  loadSampleBenchmarkDataset: vi.fn(),
  investigateFinancialDataset: vi.fn(),
  fetchFinancialSubgraph: vi.fn().mockResolvedValue({
    nodes: [
      { id: "ACC_ALPHA", label: "ACC_ALPHA", type: "Account" },
      { id: "ACC_BETA", label: "ACC_BETA", type: "Account" },
      { id: "TX_001", label: "$10,000", type: "Transaction" },
      { id: "DEV_IPHONE_99", label: "DEV_IPHONE_99", type: "Device" },
      { id: "198.51.100.12", label: "198.51.100.12", type: "IPAddress" },
    ],
    edges: [
      { id: "e1", source: "ACC_ALPHA", target: "ACC_BETA", label: "SENDS_TO", evidence_type: "DIRECT_EDGE" },
      { id: "e2", source: "ACC_ALPHA", target: "DEV_IPHONE_99", label: "USES_DEVICE", evidence_type: "DIRECT_EDGE" },
    ],
    total_nodes: 5,
    total_edges: 2,
  }),
  fetchModules: vi.fn().mockResolvedValue([]),
  fetchSubgraph: vi.fn().mockResolvedValue({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 }),
  runInvestigation: vi.fn(),
  triggerIngestion: vi.fn(),
  fetchRepositories: vi.fn().mockResolvedValue([]),
  cloneAndIngest: vi.fn(),
  refreshRepository: vi.fn(),
  fetchSourceMetadata: vi.fn().mockResolvedValue(null),
  fetchRepositorySnapshot: vi.fn().mockResolvedValue(null),
  fetchPanelExplanation: vi.fn().mockResolvedValue({
    summary: "Graph visualization explanation",
    what_you_are_looking_at: "Nodes and edges",
    what_nexusact_found: "Entities",
    why_it_matters: "Risk insights",
    evidence_and_relationships: [],
    confidence_and_limitations: "Read only",
    recommended_next_step: "Review",
    provider_status: "gemini",
    cache_key: "cache:123",
    model_name: "gemini-2.5-pro",
  }),
}));

describe("Phase 21 — Real-Data Financial Fraud Investigation UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders persistent visual semantics node legend with financial entity colors", () => {
    const mockSubgraph: SubgraphResponse = {
      nodes: [
        { id: "acc:1", label: "ACC_1", type: "Account" },
        { id: "tx:1", label: "TX_1", type: "Transaction" },
        { id: "dev:1", label: "DEV_1", type: "Device" },
        { id: "ip:1", label: "1.1.1.1", type: "IPAddress" },
        { id: "merch:1", label: "Shop", type: "Merchant" },
      ],
      edges: [
        { id: "e1", source: "acc:1", target: "tx:1", label: "EXECUTED", evidence_type: "DIRECT_EDGE" },
      ],
      total_nodes: 5,
      total_edges: 1,
    };

    render(<GraphCanvas data={mockSubgraph} />);

    // Assert that the Legend bar and all entity types are rendered
    expect(screen.getByText(/Legend:/i)).toBeDefined();
    expect(screen.getAllByText(/Account/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Transaction/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Device/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/IP Address/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Merchant/i).length).toBeGreaterThan(0);
  });

  it("renders FraudInvestigationPanel with header, dataset selector and sample loader", async () => {
    await React.act(async () => {
      render(<FraudInvestigationPanel />);
    });

    // Check heading and core action controls
    expect(screen.getByText("Fraud Investigation")).toBeDefined();
    expect(screen.getByText(/Load Benchmark/i)).toBeDefined();
    expect(screen.getByText(/Import Dataset/i)).toBeDefined();
  });

  it("enforces context isolation so codebase Git commit and repo overview do not leak on fraud tab", async () => {
    // When InvestigationWorkspace is mounted with initialTab="fraud",
    // the codebase summary cards and findings are isolated.
    await React.act(async () => {
      render(
        <InvestigationWorkspace
          selectedRepoId="repo:local_nexusact"
          initialTab="fraud"
        />
      );
    });

    // Codebase metrics shouldn't show up in fraud workspace
    expect(screen.queryByText(/Dependent Callers/i)).toBeNull();
    expect(screen.queryByText(/Topological Blast Radius/i)).toBeNull();
    expect(screen.queryByText(/Investigation Findings: Repository Scope/i)).toBeNull();
  });
});
