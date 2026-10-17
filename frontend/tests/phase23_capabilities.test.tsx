import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatAssistantDrawer } from "../src/features/investigation/ChatAssistantDrawer";
import { CounterfactualDiff } from "../src/features/investigation/CounterfactualDiff";
import { ReviewerRankings } from "../src/features/investigation/ReviewerRankings";
import * as apiClient from "../src/api/client";
import type {
  SimulationCandidate,
  ReviewersQueryResponse,
  ChatInvestigationResponse,
} from "../src/types/investigation";

vi.mock("../src/api/client", async () => {
  const actual = await vi.importActual("../src/api/client");
  return {
    ...actual,
    sendInvestigationChat: vi.fn(),
  };
});

describe("Phase 23 — Scenario Simulation, Reviewers Intelligence & AI Chat Drawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders CounterfactualDiff candidate module selector and Run Counterfactual Simulation button", () => {
    const mockCandidates: SimulationCandidate[] = [
      { id: "mod:app.main", name: "app.main", path: "app/main.py", in_degree: 5, out_degree: 8, is_entrypoint: false },
      { id: "mod:app.core", name: "app.core", path: "app/core.py", in_degree: 12, out_degree: 2, is_entrypoint: false },
    ];
    const onRun = vi.fn();

    render(
      <CounterfactualDiff
        simulation={null}
        activeView="baseline"
        onToggleView={() => {}}
        candidates={mockCandidates}
        onRunSimulation={onRun}
      />
    );

    expect(screen.getByText(/Awaiting Counterfactual Simulation/i)).toBeDefined();
    expect(screen.getByText(/app.core \(callers: 12, deps: 2\)/i)).toBeDefined();

    const runBtn = screen.getByRole("button", { name: /Run Counterfactual Simulation/i });
    expect(runBtn).toBeDefined();
    fireEvent.click(runBtn);
    expect(onRun).toHaveBeenCalledWith("mod:app.main");
  });

  it("renders ReviewerRankings with author-based recommendation transparency and commit touches", () => {
    const mockResponse: ReviewersQueryResponse = {
      repo_id: "repo:local_nexusact",
      graph_name: "nexusact_main",
      target_module_id: "mod:app.main",
      candidates: [
        {
          person_id: "person:1",
          name: "Test Contributor",
          email: "test@example.com",
          commits_count: 7,
          files_touched_count: 4,
          composite_score: 0.92,
          rank: 1,
          rationale: "Modified 4 files across 7 commits.",
          is_lead: true,
          touched_files: ["app/main.py"],
          relevant_commits: ["c1", "c2"],
        },
      ],
      total_repo_authors: 3,
      has_explicit_reviews: false,
      scoring_formula: "composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews",
      explanation: {
        summary: "Lead contributor is Test Contributor.",
        what_you_are_looking_at: "Reviewer rankings",
        what_nexusact_found: "1 ranked author",
        why_it_matters: "Domain expertise",
        evidence_and_relationships: [],
        confidence_and_limitations: "Grounded in git log",
        recommended_next_step: "Review files",
        provider_status: "fallback",
        cache_key: "k1",
      },
    };

    render(<ReviewerRankings queryResponse={mockResponse} />);

    expect(screen.getByText(/Test Contributor/i)).toBeDefined();
    expect(screen.getByText(/7 commits/i)).toBeDefined();
    const touchedBadges = screen.getAllByText((_, el) => el?.textContent?.includes("4 files touched") ?? false);
    expect(touchedBadges.length).toBeGreaterThan(0);
    expect(screen.getByText(/Author-based recommendations/i)).toBeDefined();
    expect(screen.getByText(/Lead Author/i)).toBeDefined();
  });

  it("renders ChatAssistantDrawer, sends question to api, and renders grounded answer with Cypher trace", async () => {
    const mockChatResponse: ChatInvestigationResponse = {
      conversation_id: "conv_123",
      repo_id: "repo:local_nexusact",
      graph_name: "nexusact_main",
      answer: "The active graph has 42 reachable modules connected by 89 dependency edges.",
      reasoning_summary: "Generated via Gemini grounded in FalkorDB query result.",
      query_traces: [
        {
          cypher_query: "MATCH (m:Module) RETURN count(m)",
          parameters: {},
          execution_time_ms: 3.4,
          rows_returned: 1,
          graph_name: "nexusact_main",
          status: "success",
        },
      ],
      evidence_references: [
        {
          entity_type: "Module",
          entity_id: "app.main",
          label: "app.main",
          panel_target: "graph",
        },
      ],
      provider_status: "fallback",
      model_name: "Deterministic Evidence Synthesizer",
      suggested_followups: ["What would break if app.main is removed?"],
    };

    (apiClient.sendInvestigationChat as any).mockResolvedValueOnce(mockChatResponse);

    render(
      <ChatAssistantDrawer
        isOpen={true}
        onClose={() => {}}
        repoId="repo:local_nexusact"
        graphName="nexusact_main"
      />
    );

    expect(screen.getByText(/NexusAct Graph Assistant/i)).toBeDefined();
    expect(screen.getByPlaceholderText(/Ask about dependencies/i)).toBeDefined();

    const textarea = screen.getByPlaceholderText(/Ask about dependencies/i);
    fireEvent.change(textarea, { target: { value: "How many modules exist?" } });

    const sendBtn = screen.getByRole("button", { name: /Send message/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText(/42 reachable modules/i)).toBeDefined();
      expect(screen.getByText(/FalkorDB Executed Cypher/i)).toBeDefined();
    });
  });
});
