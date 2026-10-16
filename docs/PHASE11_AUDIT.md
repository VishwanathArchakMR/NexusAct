# NEXUSACT — PHASE 11 AUDIT & ACCEPTANCE MATRIX
**Product:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Track:** Agents That Act on Connected Data  
**Primary Graph Database:** FalkorDB v4.4.1  
**Audit Date:** 2026-10-17  

---

## 1. Executive Baseline & Diagnostic Summary

### 1.1 Root Cause of Blank Graph Canvas (Release Blocker)
- **Symptom:** In the investigation workspace, the header reported 406 nodes and 631 edges, but the canvas rendered completely blank or as a squashed invisible sliver.
- **Root Cause 1 (Internal Integer ID Mismatch in Backend Endpoint):**
  - In `backend/app/api/endpoints/investigation.py` (`/graph/subgraph`), when `center_module_id` was provided, `src_id` and `dst_id` were extracted as `str(r.src_node)` and `str(r.dest_node)`.
  - In FalkorDB Cypher, `r.src_node` and `r.dest_node` return FalkorDB's internal integer node IDs (e.g. `4`, `26`).
  - Meanwhile, `GraphNode` objects in `nodes_map` were keyed and identified by their business property ID (`props.get("id")`, e.g. `"mod:backend.app.main"`).
  - Consequently, in `GraphCanvas.tsx`, `nodes.find(n => n.id === edge.source)` evaluated to `undefined` for every single edge. Zero edges were rendered.
- **Root Cause 2 (Lane BFS Failure & Extreme SVG Aspect Squashing):**
  - Because `edge.source` and `edge.target` had integer IDs while `targetId` was a business ID (`"mod:..."`), BFS in `assignLanes()` never traversed any edges.
  - All nodes fell back to `lane 0`.
  - With 406 nodes stacked vertically in a single column, computed canvas height reached 27,000+ px.
  - Squeezing a 700x27000 coordinate space into a 430px fixed container squashed all SVG elements into a sub-pixel microscopic sliver centered on screen.
- **Resolution Plan:**
  1. Map internal integer node IDs to business `id` properties in `investigation.py` (`get_graph_subgraph`).
  2. Overhaul `GraphCanvas.tsx` to provide responsive SVG scaling, pan/zoom controls, fit-to-view, neighborhood bounding, search, node/edge inspection, and light/dark theme support.

### 1.2 Root Cause of CI Failure (Run `38946385411`)
- **Symptom:** `test_phase10_test_b_two_different_repositories` failed on assertion: `assert len(nodes_b) > 0, "LifeAssist graph should contain modules"`.
- **Root Cause:** In Phase 10, `repo:vishwanatharchakmr_lifeassist_ai` was ingested locally on workstation into `repo_vishwanatharchakmr_lifeas`. In clean GitHub Actions CI, FalkorDB runs as a fresh container where `repo_vishwanatharchakmr_lifeas` is not pre-seeded and network cloning is not executed during test execution.
- **Resolution Plan:**
  1. Provide a deterministic TypeScript/JavaScript repository fixture in `tests/fixtures/typescript_repo/`.
  2. Implement a deterministic seeding helper `seed_typescript_fixture()` that ingests this fixture into an isolated test graph (`repo_test_typescript_fixture`).
  3. Update `test_phase10_input_driven_gaf.py` to test multi-repository isolation against deterministic fixtures in CI, leaving live network cloning as an opt-in test.

---

## 2. Compact Hackathon Acceptance Matrix

| Hackathon Requirement | Target Specification | Implementation Artifacts | Verification Method / Tests | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Multi-Hop Graph Reasoning** | Real multi-hop path tracing across `>=2` connected edges; directional graph traversal. | `backend/app/graph/tools/impact.py`<br>`backend/app/graph/tools/paths.py`<br>`frontend/src/features/investigation/GraphCanvas.tsx` | `tests/integration/test_phase6_mcp_tools.py`<br>GraphCanvas path highlighting | In Progress (Backend verified, UI wiring in Phase 11) |
| **2. Graph Queries & Algorithms as Tools** | PageRank, Reverse Dependency Impact, Shortest Path, Who Knows, Counterfactual Simulation. | `backend/app/graph/tools/*`<br>`backend/app/agent/tools.py` | `tests/integration/test_phase6_mcp_tools.py`<br>`test_phase4_simulation.py` | Verified (All 5 tools operational on FalkorDB) |
| **3. Adaptive MCP Tool Selection** | Natural-language query drives bounded dynamic tool execution plan, returning trace with rationale. | `backend/app/agent/planner.py`<br>`frontend/src/features/investigation/AgentTrace.tsx` | Query-dependent tool trace tests in `test_phase6_investigation_api.py` | Verified (Heuristic fallback + adaptive planner) |
| **4. Actions Grounded in Evidence** | Verified actions proposed with cryptographic payload hash, target module, revision, and approval gate. | `backend/app/agent/verifier.py`<br>`backend/app/api/endpoints/action.py`<br>`frontend/src/features/investigation/IssueProposalCard.tsx` | `tests/integration/test_phase5_action_gate.py` | Verified (Fail-safe GitHub write protection intact) |
| **5. Investigation Summary & Explainability** | First-class structured summary answering Question, Scope, Approach, Findings, Risk, Recommendations. | `backend/app/agent/planner.py`<br>`frontend/src/features/investigation/InvestigationWorkspace.tsx` | Verification banner, metrics, and summary card in workspace | In Progress (Enhancing visual summary in Phase 11) |
| **6. Connected Data & Repository Isolation** | Strict isolation between repositories (`nexusact_main`, `repo_*`) and public corpus (`nexusact_public`). | `backend/app/sources/registry.py`<br>`backend/app/api/endpoints/discovery.py` | `tests/integration/test_phase10_input_driven_gaf.py` | Fix clean CI deterministic fixture |
| **7. Visible Graph Exploration** | Canvas visibly renders nodes and directed edges with pan/zoom, node details, and light/dark theme. | `frontend/src/features/investigation/GraphCanvas.tsx`<br>`frontend/src/index.css` | Vitest, browser validation, visual inspection | Active Focus (Part 3 & 4) |
| **8. Memory & Investigation Continuity** | Persistent historical investigations inspectable across sessions without leaking cross-repo data. | `backend/app/graph/persister.py`<br>`backend/app/api/endpoints/investigation.py` | `tests/integration/test_phase10_input_driven_gaf.py` | Verified |
| **9. Clean CI Quality Gate** | Passing Ruff, Mypy, Pytest, Oxlint, Vitest, Vite Build, Docker Build on clean GitHub Actions runner. | `.github/workflows/ci.yml`<br>`scripts/check.ps1` | GitHub Actions workflow run verification | Active Focus (Part 10) |
