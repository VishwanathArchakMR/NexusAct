# NexusAct — Phase 8 Completion Report
**Product:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Subtitle:** Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Primary Database:** FalkorDB v4.4.1 (container `nexusact_falkordb`, port 6379)  
**Execution Phase:** Phase 8 — Graph Truth, Investigation Repair, Public-Data Integration, and Product Validation  
**Date:** 2026-10-16  

---

## 1. Executive Summary & Verification Outcomes

Phase 8 eliminated the gap between user-facing presentation and verified backend/graph truth. Every identified runtime issue—from CORS origin rejections on `http://localhost:5174`, to stale investigation results masquerading as evidence on empty repositories, to Universal Ask GAF stop-word keyword starvation and duplicate React keys—has been resolved and verified with deterministic tests.

### Concrete Status by Layer
| Domain | Claimed Status | Actual Realized Status | Verification Mechanism |
| :--- | :--- | :--- | :--- |
| **CORS & Dev Origin** | Resolved | **Implemented, Tested & Verified** | `test_phase8_cors_and_connectivity.py` (4/4 tests passed) |
| **API Connectivity & Health** | Resolved | **Implemented, Tested & Verified** | 60s TTL cache on connector health, bounded 3s timeouts |
| **Investigation Ownership** | Resolved | **Implemented, Tested & Verified** | Canonical `repository_id`, `graph_name`, `commit_sha` on `InvestigationReport` |
| **Stale State Invalidation** | Resolved | **Implemented, Tested & Verified** | UI wipes `report`, `selectedModule`, and `error` on repo change; blocks cross-repo displays |
| **LifeAssist Ingestion Diagnosis**| Resolved | **Implemented, Tested & Verified** | Honest gap reporting in `data_gaps` for non-Python repositories (`test_phase8_graph_truth_and_unresolved.py`) |
| **Structured Unresolved Target** | Resolved | **Implemented, Tested & Verified** | `status="UNRESOLVED"` with candidate suggestions; zero fabricated paths |
| **Software Investigation Tabs** | Complete | **Implemented, Tested & Verified** | All 7 tabs render verified data or honest empty states |
| **Universal Keyword Extraction** | Complete | **Implemented, Tested & Verified** | Refined stop-words; entity-type and intent-aware routing |
| **Canonical Entity Deduplication**| Complete | **Implemented, Tested & Verified** | Canonical DOI normalization across OpenAlex & Crossref; unique directed edges |
| **React Key Integrity** | Complete | **Implemented, Tested & Verified** | UI node deduplication in `GraphCanvas` and `UniversalDiscoveryWorkspace` (`phase8_react_keys_and_ownership.test.tsx`) |
| **Automated Pytest Suite** | 81 tests passing | **81 Passed (100%)** | `pytest -v` (81 passed in 21s) |
| **Frontend Test Suite** | 10 tests passing | **10 Passed (100%)** | `vitest run` (10 passed in 2.6s) |
| **Frontend Production Build** | Zero errors | **Verified Succeeded** | `tsc -b && vite build` (dist generated in 567ms) |
| **Quality Check Gate** | Zero warnings/errors | **All Checks Passed** | `.\scripts\check.ps1` (ruff, mypy, pytest, oxlint, vitest, build) |

---

## 2. Root Cause Analysis & Proof of Fixes

### A. CORS & API Connectivity Defect
- **Problem**: When `http://localhost:5173` was busy, Vite launched on `http://localhost:5174`. Starlette's `CORSMiddleware` rejected all API requests from `http://localhost:5174` because port 5174 was absent from `CORS_ORIGINS`.
- **Root Cause**: `backend/app/core/config.py` had a static list of ports (5173, 3000) with no regex support for local loopback development ports.
- **Fix Applied**:
  1. Updated `CORS_ORIGINS` defaults in `backend/app/core/config.py` to include `http://localhost:5174` and `http://127.0.0.1:5174`.
  2. Added `cors_origin_regex` property to `Settings`: in development mode (`APP_ENV == "development"`), it safely matches `r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$"`. In production mode (`APP_ENV == "production"`), it returns `None`, enforcing strict explicit origin whitelisting.
  3. Updated `backend/app/main.py` to install `CORSMiddleware` with `allow_origin_regex=settings.cors_origin_regex`.
  4. Added regression test `tests/integration/test_phase8_cors_and_connectivity.py` testing GET, preflight OPTIONS, loopback IPs, untrusted origin rejection, and production strictness.

### B. LifeAssist Ingestion & Stale Investigation Claims
- **Problem**: Ingesting `LifeAssist_AI` (commit `47dd300`) showed 0 modules and 0 dependency edges, yet the UI displayed `VERIFIED: 27 upstream callers, 40 broken paths, 24 surviving paths` with a target resolution error for `mod:backend.app.graph.client`.
- **Root Cause**:
  1. `LifeAssist_AI` is a TypeScript/React repository (`package.json`, `App.tsx`, `triageService.ts`) with no `.py` files. `RepositoryAstParser` is strictly a Python AST parser and discovered 0 eligible files. It completed with 0 modules and 0 edges, but gave no diagnostic explanation.
  2. `InvestigationWorkspace.tsx` retained the previous successful report from `nexusact_main` when switching the active repository dropdown, leading to an inconsistent UI state.
  3. When an investigation was triggered for a module that did not exist in the selected graph, `AdaptiveInvestigationAgent.investigate` raised an uncaught `ValueError`, generating HTTP 400 rather than an honest structured report.
- **Fix Applied**:
  1. In `backend/app/ingestion/engine.py`, added honest diagnostic reporting to `data_gaps`: when no `.py` files exist, it records: *"No supported Python source files (.py) found in repository. TypeScript, JavaScript, and non-Python source files are not currently parsed into code dependency modules."*
  2. Fixed `resolved_repo_id` binding in `engine.py` line 127 so ingested modules link directly to their registered repository node.
  3. In `backend/app/agent/planner.py`, updated `InvestigationReport` with `commit_sha: Optional[str]` and `unresolved_reason: Optional[str]`. When a target cannot be resolved in `target_graph`, it queries candidates and returns a structured `InvestigationReport(status="UNRESOLVED", summary=..., ambiguity_candidates=...)` with zero fabricated paths or callers (`impact_result=None`, `simulation_result=None`).
  4. In `frontend/src/features/investigation/InvestigationWorkspace.tsx`, on repository switch, `report` is immediately cleared (`setReport(null)`), `selectedModule` is reset, and `error` is cleared. A guard prevents reports belonging to other repositories from rendering, and candidate buttons are rendered to help the user select valid modules.

### C. Universal Ask GAF Keyword Starvation, Health Flooding & Duplicate Keys
- **Problem**: All 4 connectors showed `ONLINE`, but natural language investigations returned `0 entities and 0 relationships across 2 public sources`. The console displayed repeated React key warnings (`openalex:10.3390/app14219690`).
- **Root Cause**:
  1. Over-aggressive stop-word list in `discovery_planner.py` removed key terms (`ai`, `model`, `dataset`, `paper`, `open-source`, `ecosystem`, `train`, `used`), reducing user queries to generic fallbacks.
  2. `ConnectorRegistry.health_status()` made live un-cached external HTTP requests on every UI poll/render, causing API throttling and timeouts.
  3. Records sharing the same DOI across OpenAlex and Crossref, or multiple records for the same paper, were appended raw into `entities_summary` and `subgraph.nodes`, producing duplicate React keys.
- **Fix Applied**:
  1. Pruned stop-words in `backend/app/agent/discovery_planner.py` to preserve core technical nouns and entity qualifiers.
  2. Added in-memory TTL caching (60s) with 3.0s bounded probe timeouts to `ConnectorRegistry.health_status()`.
  3. Implemented canonical entity deduplication in `discovery_planner.py`: papers are keyed by normalized DOI (`doi:<doi>`), and other entities by `source_id:external_id`. Relationship endpoints are mapped to canonical IDs, deduplicating directed edge tuples `(canon_src, rel_type, canon_tgt)`.
  4. Added `RETURN DISTINCT` to Cypher queries in `backend/app/sources/graph_persister.py`.
  5. In `frontend/src/features/investigation/GraphCanvas.tsx` and `frontend/src/features/discovery/UniversalDiscoveryWorkspace.tsx`, implemented UI-level deduplication using `Array.from(new Map(...))` before rendering.

---

## 3. Working State of Software Investigation Tabs

Every tab in the software investigation workspace adheres to a verified contract backed by FalkorDB:

1. **Dependency Graph (`GraphCanvas.tsx`)**:
   - Queries `nexusact_get_subgraph`. Displays real modules and `DEPENDS_ON` edges.
   - Layout deduplicates visible nodes and edges.
   - Honest empty state: *"No graph nodes selected. Select a module or run an investigation to render the live dependency graph."*
2. **Counterfactual Diff (`CounterfactualDiff.tsx`)**:
   - Executes `nexusact_simulate_remove_module` on an isolated graph clone (`scenario_*`).
   - Proves original graph remains untouched.
   - Displays baseline paths count, disappeared paths, surviving paths, newly isolated modules, and static topological blast radius score.
3. **Reviewer Evidence (`ReviewerRankings.tsx`)**:
   - Executes `nexusact_who_knows` querying `AUTHORED` commits from real git history.
   - Computes transparent composite scores with breakdown (files touched, recency, ownership).
   - Explicitly displays `missing_evidence` callouts (e.g. *"PR peer review records unavailable in local Git log"*).
4. **Agent MCP Trace (`AgentTrace.tsx`)**:
   - Records every executed MCP tool step (`nexusact_trace_impact`, `nexusact_who_knows`, `nexusact_page_rank`, `nexusact_simulate_remove_module`).
   - Displays tool arguments, execution duration in ms, and step status.
   - Distinguishes adaptive LLM decision-making from deterministic heuristic fallback.
5. **Neighborhood & Paths**:
   - Traverses 1-hop upstream and downstream nodes with verified relationship types.
   - Shows candidate modules when resolving ambiguous terms.
6. **Source Provenance**:
   - Links modules to source file paths, git commits, and timestamps.
7. **Verified Action**:
   - Enforces approval-bound proposal workflow.
   - Proposes actionable remediations with dry-run read-back before external issue creation.

---

## 4. End-to-End Acceptance Scenarios (Phase I)

### Scenario 1: Healthy Local Application
- Backend running on `http://127.0.0.1:8000`, Frontend on `http://localhost:5174` (or 5173).
- Health check `GET /api/v1/health/liveness` returns `{"status":"ok"}`.
- Readiness check `GET /api/v1/health/readiness` confirms `{"database":"online","status":"ready"}`.
- CORS preflight `OPTIONS /api/v1/health/liveness` with `Origin: http://localhost:5174` returns `Access-Control-Allow-Origin: http://localhost:5174`.

### Scenario 2: Software Graph Integrity & LifeAssist Ingestion
- Multi-module Python fixture ingests with exact module count, dependency edges, and git history.
- LifeAssist repository onboarding parses 0 `.py` files and records explicit diagnostic gap: *"No supported Python source files (.py) found in repository. TypeScript, JavaScript, and non-Python source files are not currently parsed into code dependency modules."*
- Zero modules and zero edges are honestly reported without fabricating nodes.

### Scenario 3: Investigation Ownership & Stale Results Invalidation
- Running an investigation on `nexusact_main` produces a valid report.
- Switching to an empty repository immediately clears the report from view.
- Attempting an investigation on a nonexistent module returns `status="UNRESOLVED"` with candidate suggestions; previous successful metrics never masquerade as evidence.

### Scenario 4: Universal Research Question
- Asking *"Which datasets are documented as used to train open-source models?"* executes bounded searches to Hugging Face and Wikidata.
- Extracted entities and relationships are persisted to `nexusact_public`.
- Multi-hop paths and evidence fields (`downloads`, `pipeline_tag`, `tags`) are inspectable.

### Scenario 5: Partial Source Outage
- When one external provider is unreachable or times out (3.0s bounded limit), the remaining providers return valid results.
- The failure is explicitly documented in `coverage_limitations` without crashing the investigation.

### Scenario 6: Duplicate Records & React Key Integrity
- Multiple search records containing identical DOIs (e.g. from OpenAlex and Crossref) are merged into a single canonical entity (`doi:<doi>`).
- React renders the list with 0 duplicate key console warnings.

### Scenario 7: Frontend State Integrity
- Switching tabs between Software Graph, Universal Ask GAF, AI Ecosystem, and Research & Citations preserves stable state without redundant network request storms.

---

## 5. Test Suite Execution & Local Quality Gate

Full validation executed via `.\scripts\check.ps1`:
```powershell
=== Running NexusAct Quality & Validation Suite ===

[1/6] Checking Python formatting and linting (ruff)...
[PASS] Ruff check passed.
[PASS] Ruff format check passed.

[2/6] Checking Python types (mypy)...
Success: no issues found in 61 source files
[PASS] Mypy type check passed.

[3/6] Running Pytest suite (Smoke, Capabilities, Integration, Unit)...
============================= 81 passed in 21.29s =============================
[PASS] All Pytest tests passed.

[4/6] Checking Frontend linting (oxlint)...
Found 0 warnings and 0 errors.
[PASS] Frontend lint passed.

[5/6] Running Frontend tests (vitest)...
Test Files  3 passed (3)
     Tests  10 passed (10)
[PASS] Frontend tests passed.

[6/6] Verifying Frontend production build...
dist/index.html                   0.51 kB │ gzip:  0.34 kB
dist/assets/index-QbNFSNGE.css    1.62 kB │ gzip:  0.79 kB
dist/assets/index-D3GexaOF.js   323.62 kB │ gzip: 91.87 kB
✓ built in 567ms
[PASS] Frontend build succeeded.

==================================================
ALL QUALITY CHECKS PASSED SUCCESSFULLY!
```

---

## 6. Known Limitations
1. **Source Parser Scope**: `RepositoryAstParser` is currently a Python-only static AST parser. Non-Python repositories (TypeScript, Rust, Go) are accurately registered with Git history, but code modules are not extracted; an honest gap note is recorded in `data_gaps`.
2. **Public Provider Rate Limits**: Hugging Face and OpenAlex free tiers enforce rate limits under rapid polling. The 60-second in-memory health cache and 3.0-second timeout protect against request storms, but live queries should remain bounded.

---

## 7. Release Commit & Git Provenance
- **Branch**: `master`
- **Baseline Commit**: `885439b`
- **Validation Status**: All local quality checks passed (100% green).
