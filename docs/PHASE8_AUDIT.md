# NexusAct — Phase 8 Comprehensive Audit & Ground-Truth Matrix

**Date**: 2026-10-16  
**Baseline Git Commit**: `885439b`  
**Target Graph Database**: FalkorDB v4.4.1 (container `nexusact_falkordb`, port 6379)  
**Primary Graphs**: `nexusact_main` (software repository), `nexusact_public` (universal GAF), isolated repository graphs (`repo_*`)

---

## 1. Executive Summary & Root-Cause Analysis

This audit examines the exact defects identified in live runtime and screenshots, contrasting claims in prior completion reports against the actual codebase and runtime behavior.

### A. CORS Rejection (`http://localhost:5174`)
- **Observed Defect**: Browser requests from `http://localhost:5174` were rejected because the backend response lacked `Access-Control-Allow-Origin`.
- **Root Cause**: `backend/app/core/config.py` hardcoded default CORS origins:
  `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000`.
  When port 5173 was busy and Vite defaulted to port 5174, requests were rejected by Starlette's `CORSMiddleware`.
- **Remediation**: Expand default development origins to include `http://localhost:5174`, `http://127.0.0.1:5174`, and in development mode (`APP_ENV == "development"`), allow dynamic loopback development origin matching (`localhost` and `127.0.0.1` ports 5173–5180). Keep production CORS origins strictly explicit.

### B. Stale Graph Claims & Empty Repository Inconsistency
- **Observed Defect**: A registered `LifeAssist_AI` repository at revision `47dd300` showed 0 modules and 0 edges, yet an investigation card displayed:
  `VERIFIED: 27 upstream callers, 40 broken paths, 24 surviving paths`, accompanied by an error stating `mod:backend.app.graph.client cannot be resolved in the selected graph`.
- **Root Cause**:
  1. **LifeAssist Ingestion**: `LifeAssist_AI` is a TypeScript/React repository (`App.tsx`, `triageService.ts`, `package.json`) with zero `.py` files. `RepositoryAstParser` is strictly a Python AST parser and discovered 0 eligible files. Git history and the repository node were ingested, but 0 modules were extracted. The ingestion report lacked an explicit diagnostic message explaining why 0 modules were found.
  2. **Frontend Stale State Retention**: `InvestigationWorkspace.tsx` failed to reset `report`, `selectedModule`, or `error` when switching repositories in `<select value={selectedRepoId}>`. Stale results from `nexusact_main` remained visible on screen.
  3. **Target Resolution Handling**: When the user requested an investigation for `mod:backend.app.graph.client` on an empty or unrelated graph, `planner.py` threw `ValueError` resulting in HTTP 400 without a structured `unresolved-target` model or candidate suggestions.
- **Remediation**:
  - Invalidate and clear prior investigation results whenever repository, graph, or revision changes.
  - Establish canonical investigation provenance in `InvestigationReport`: `investigation_id`, `repository_id`, `graph_name`, `commit_sha`, `target_module_id`, `timestamp`, and verification failure reasons.
  - Enforce graph-scoped evidence verification: never label an empty graph or unresolved target as `VERIFIED`. Return structured unresolved-target diagnostics with candidate entities.
  - In `engine.py`, add explicit diagnostic gap reporting when 0 Python modules are detected, and fix repository-to-module linking query parameter.

### C. Universal Ask GAF Zero Results & Duplicate Keys
- **Observed Defect**: All four public connectors showed `ONLINE`, but an investigation returned `0 entities and 0 relationships across 2 public sources`. The console reported duplicate React keys: `openalex:10.3390/app14219690`.
- **Root Cause**:
  1. **Aggressive Stop-Word Removal**: `discovery_planner.py` had an over-aggressive stop-word filter containing `ai`, `model`, `dataset`, `paper`, `open-source`, `ecosystem`, `train`, `used`. When querying questions like *"Which datasets are used to train open-source models?"*, all keywords were stripped, forcing fallback to `"transformer"` across all connectors regardless of query intent.
  2. **Lack of Connector Health Caching**: `/api/v1/discover/sources` executed live un-cached HTTP calls to all 4 external APIs on every component mount/tab switch, causing request storms, timeouts, and frontend failure cascades.
  3. **Duplicate Entities & React Keys**: Search results containing duplicate records across pages/connectors were appended without canonical deduplication, producing identical keys in `entities_summary` and `subgraph.nodes`.
- **Remediation**:
  - Refine keyword extraction and query-intent routing: detect entity types (Model, Dataset, Paper, Organization, Person) and query only suitable providers with intent-appropriate terms.
  - Implement short-lived caching (60s TTL) with bounded 3s timeouts for source connector health checks.
  - Implement canonical entity deduplication in `UniversalDiscoveryPlanner` and safe key generation in React components.

---

## 2. Feature-to-Implementation Matrix

| Feature / Domain | Backend Implementation | Frontend Implementation | FalkorDB Verification | Current Status | Planned Phase 8 Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CORS & Dev Host** | `backend/app/core/config.py`, `backend/app/main.py` | `frontend/src/config/env.ts`, `vite.config.ts` | N/A | **Defective** (5174 rejected) | Add 5174 + dev loopback regex, add regression test |
| **API Client & Routing** | `backend/app/main.py` | `frontend/src/api/client.ts` | N/A | **Working** (direct CORS) | Keep direct API contract, eliminate redundant fetches |
| **Multi-Repo Management** | `backend/app/sources/registry.py`, `ingestion.py` | `InvestigationWorkspace.tsx` | `repo_*` isolated graphs | **Partially Defective** (stale UI state) | Reset state on repo change, fix repo ID binding |
| **Python AST Parser** | `backend/app/ingestion/ast_parser.py`, `engine.py` | `InvestigationWorkspace.tsx` | `Module`, `File`, `DEPENDS_ON` | **Working for Python** (needs TS/JS honesty) | Add explicit non-Python gap diagnosis |
| **Target Resolver** | `backend/app/graph/tools/resolve.py`, `planner.py` | `InvestigationWorkspace.tsx` | Cypher prefix/fuzzy match | **Partially Defective** (crashes to 400) | Return structured unresolved-target response |
| **Evidence Verifier** | `backend/app/evidence/verifier.py` | `InvestigationWorkspace.tsx` | Cypher path validation | **Working** (needs graph-scoping) | Prevent `VERIFIED` on empty/unresolved graphs |
| **Counterfactual Diff** | `backend/app/graph/tools/simulation.py` | `CounterfactualDiff.tsx` | Isolated graph copy | **Working** | Verify clean isolation and honest reachability |
| **Reviewer Evidence** | `backend/app/graph/tools/reviewers.py` | `ReviewerRankings.tsx` | `Person`, `Commit`, `AUTHORED` | **Working** | Empty state when no git/PR history exists |
| **Agent MCP Trace** | `backend/app/agent/planner.py`, `mcp_server` | `AgentTrace.tsx` | `Investigation`, `ToolInvocation` | **Working** | Clarify heuristic vs LLM mode in trace |
| **Universal Connectors** | `backend/app/sources/connectors/*` | `UniversalDiscoveryWorkspace.tsx` | `nexusact_public` | **Partially Defective** (stop-words & keys) | Fix stop-words, deduplicate entities and React keys |
| **FalkorDB Public Graph** | `backend/app/sources/graph_persister.py` | `UniversalDiscoveryWorkspace.tsx` | `nexusact_public` | **Working** | Ensure DISTINCT queries and canonical node upserts |

---

## 3. Detailed Work Plan

1. **Phase B (CORS & Connectivity)**:
   - Update `config.py` and `main.py` to support `http://localhost:5174`, `http://127.0.0.1:5174`, and dev loopback port patterns.
   - Add backend CORS unit test verifying `http://localhost:5174` (GET and OPTIONS).
   - Add health check caching in `ConnectorRegistry` to stop request storms.
2. **Phase C (Graph Truth & Stale Claims)**:
   - Update `InvestigationReport` with canonical provenance fields (`repository_id`, `graph_name`, `commit_sha`, `is_unresolved`).
   - Fix target resolution in `planner.py` to produce structured unresolved reports rather than unhandled 400s.
   - Update `InvestigationWorkspace.tsx` to wipe stale reports, targets, and errors on repository switch.
   - Update `engine.py` to provide honest diagnostic notes when 0 Python files are found in a repo, and fix `repo_id` binding.
3. **Phase D (Software Investigation Tabs)**:
   - Audit and verify all 7 tabs for empty graph states, candidate target selection, and honest non-fabricated output.
4. **Phase E & F (Universal Ask GAF & Public Data)**:
   - Refactor keyword extraction in `discovery_planner.py` to preserve crucial technical terms.
   - Deduplicate entities canonically by `(source_id, external_id)` and DOI.
   - Add key deduplication in `UniversalDiscoveryWorkspace.tsx`.
5. **Phase G & H (Frontend & CI Reconciliation)**:
   - Ensure complete TypeScript type safety and vitest pass.
   - Run full backend pytest suite (all tests passing against FalkorDB).
   - Validate Docker compose and image builds.
6. **Phase I & K (Scenarios & Final Completion Report)**:
   - Verify End-to-End Acceptance Scenarios 1–7.
   - Create `docs/PHASE8_COMPLETION_REPORT.md` and commit/push to `origin/master`.
