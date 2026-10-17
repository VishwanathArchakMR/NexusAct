import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { CodeInspector } from "../src/features/investigation/CodeInspector";

const mockFileTree = {
  repository_id: "repo:local_nexusact",
  repository_name: "NexusAct",
  commit_sha: "3c2b1f9a217f",
  total_files: 3,
  total_directories: 2,
  tree: [
    {
      name: "backend",
      path: "backend",
      type: "directory" as const,
      children: [
        {
          name: "app",
          path: "backend/app",
          type: "directory" as const,
          children: [
            {
              name: "main.py",
              path: "backend/app/main.py",
              type: "file" as const,
              language: "python",
              has_graph_module: true,
              module_id: "mod:backend.app.main",
            },
            {
              name: "router.py",
              path: "backend/app/router.py",
              type: "file" as const,
              language: "python",
              has_graph_module: true,
              module_id: "mod:backend.app.router",
            },
          ],
        },
      ],
    },
    {
      name: "README.md",
      path: "README.md",
      type: "file" as const,
      language: "markdown",
      has_graph_module: false,
    },
  ],
  truncated: false,
};

const mockFileContent = {
  file_path: "backend/app/main.py",
  repository_id: "repo:local_nexusact",
  commit_sha: "3c2b1f9a217f",
  start_line: 1,
  end_line: 5,
  total_lines: 5,
  content: 'import fastapi\n\ndef create_app():\n    return fastapi.FastAPI()\n\napp = create_app()',
  language: "python",
  symbols: [
    {
      name: "create_app",
      kind: "function" as const,
      start_line: 3,
      end_line: 4,
      signature: "create_app()",
      docstring: "Initializes FastAPI application instance.",
    },
  ],
  graph_linkage: {
    has_graph_module: true,
    module_id: "mod:backend.app.main",
    module_name: "backend.app.main",
    dependencies: ["backend.app.router", "backend.app.core.config"],
    dependents: ["tests.integration.test_api"],
    modeled_level: "module_level",
  },
};

vi.mock("../src/api/client", () => ({
  fetchFileTree: vi.fn().mockImplementation(() => Promise.resolve(mockFileTree)),
  fetchFileContent: vi.fn().mockImplementation(() => Promise.resolve(mockFileContent)),
}));

describe("Phase 16 — Code Inspector & Project Explorer Workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 3-part layout with Project Explorer, Source Viewer, and Symbol/Graph Inspector", async () => {
    await React.act(async () => {
      render(
        <CodeInspector
          repoId="repo:local_nexusact"
          commitSha="3c2b1f9a217f"
        />
      );
    });

    // Left explorer header and files
    expect(screen.getByPlaceholderText(/Filter files.../i)).toBeDefined();
    expect(screen.getAllByText("main.py").length).toBeGreaterThan(0);

    // Center viewer shows content
    expect(screen.getAllByText(/create_app/i).length).toBeGreaterThan(0);

    // Right inspector shows symbols and graph provenance
    expect(screen.getByText(/Graph Modeling & Provenance/i)).toBeDefined();
    expect(screen.getByText(/Modeled in FalkorDB/i)).toBeDefined();
    expect(screen.getByText(/Symbol Outline/i)).toBeDefined();
    expect(screen.getByText(/Connected Graph Neighbors/i)).toBeDefined();
  });

  it("filters tree when user types in search box", async () => {
    await React.act(async () => {
      render(
        <CodeInspector
          repoId="repo:local_nexusact"
          commitSha="3c2b1f9a217f"
        />
      );
    });

    const searchInput = screen.getByPlaceholderText(/Filter files.../i);
    await React.act(async () => {
      fireEvent.change(searchInput, { target: { value: "router" } });
    });

    // router.py matches
    expect(screen.getByText("router.py")).toBeDefined();
    // README.md does not match
    expect(screen.queryByText("README.md")).toBeNull();
  });

  it("highlights line range when symbol is selected in symbol outline", async () => {
    await React.act(async () => {
      render(
        <CodeInspector
          repoId="repo:local_nexusact"
          commitSha="3c2b1f9a217f"
        />
      );
    });

    // Click symbol in symbol outline
    const symbolBtns = screen.getAllByText("create_app");
    await React.act(async () => {
      fireEvent.click(symbolBtns[symbolBtns.length - 1]);
    });


    // Center header shows active focus lines
    expect(screen.getByText(/Focus: Lines 3–4 \(create_app\)/i)).toBeDefined();
  });

  it("triggers context investigation action with current file context", async () => {
    const onTriggerSpy = vi.fn();
    await React.act(async () => {
      render(
        <CodeInspector
          repoId="repo:local_nexusact"
          commitSha="3c2b1f9a217f"
          onTriggerInvestigation={onTriggerSpy}
        />
      );
    });

    // Click "Assess Change Impact" action
    const impactBtn = screen.getByText(/Assess Change Impact/i);
    await React.act(async () => {
      fireEvent.click(impactBtn);
    });

    expect(onTriggerSpy).toHaveBeenCalledWith(
      expect.stringContaining("What could break if I modify or delete"),
      "mod:backend.app.main"
    );
  });
});
