# NexusAct — Phase 17 Final Engineering Report

**Date:** October 17, 2026  
**Competition:** Graph Hacks — WeMakeDevs × FalkorDB  
**Primary Track:** *Agents That Act on Connected Data*  
**Architecture:** GraphAction Fabric (GAF)  
**Primary Database:** FalkorDB v4.4.1  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  

---

## 1. Executive Summary

Phase 17 elevates NexusAct into an intuitive, explainable, and visually rich **Graph Intelligence Workspace**. By uniting FalkorDB's property graph traversal with grounded Gemini reasoning, distinct topological visual semantics, and persistent lossless workspace navigation, NexusAct makes complex software and financial graph investigations clear, verifiable, and actionable:

1. **Persistent Left-Side Vertical Sidebar Navigation:**
   Rebuilt the workspace navigation as a collapsible, categorized left sidebar:
   - **Explore:** Graph Explorer (`graph`), Code Inspector (`code`).
   - **Analyze:** Counterfactual Simulation (`simulation`), Reviewers & Ownership (`reviewers`), Agent Trace (`trace`), 1-Hop Neighborhood (`neighborhood`).
   - **Evidence & Action:** Source Provenance (`provenance`), Action Execution (`action`).
   - **Specialized Workflows:** Security Triage (OSV) (`security`), Financial Graph Fraud (`fraud`).

2. **Lossless View State Preservation:**
   - Switched from destructive conditional unmounting (`{activeTab === 'graph' && <GraphCanvas />}`) to persistent CSS-controlled rendering (`display: activeTab === 'graph' ? 'flex' : 'none'`).
   - Zoom level, pan coordinates, selected nodes, active tabs, and open files in `CodeInspector` are 100% retained when navigating between panels.

3. **Evidence-Grounded Explanations (Gemini + Rule-Based Fallback):**
   - Implemented `POST /api/v1/investigation/explain-panel` powered by `backend/app/agent/explanation.py` and `backend/app/agent/llm.py`.
   - Explains technical graph findings in plain English structured into 6 sections:
     - **Summary** & **What You Are Looking At**
     - **What NexusAct Found** & **Why It Matters**
     - **Evidence & Grounded Facts**
     - **Confidence & Limitations** & **Recommended Next Step**
   - Seamlessly uses Google Gemini when `GEMINI_API_KEY` is present, with deterministic domain-grounded fallbacks and LRU in-memory caching (`investigation_id:commit_sha:panel_id:data_hash`).
   - Strict security: `GEMINI_API_KEY` is exclusively managed on the backend and is never exposed to the browser.

4. **Visual & Semantic Graph Upgrade:**
   - Rendered distinct SVG geometries by node type:
     - **Module:** Rounded rectangular chip with category badge.
     - **File:** Document card with folded corner.
     - **Vulnerability:** Diamond shape with warning indicator.
     - **Contributor / Author:** Circular portrait silhouette.
     - **Account / Device:** Cylindrical pill.
   - Enhanced edge visual semantics:
     - Solid stroke for **Observed** AST imports.
     - Dashed stroke (`6,4`) for **Derived** counterfactual and reachability paths.
     - Dotted stroke (`2,3`) for **Inferred** synthetic and heuristic connections.
     - Relationship labels rendered in contrast-safe midpoint pills.
   - Dedicated horizontal sequential layout for **Investigation Path View** (`graphViewMode === "path"`).

5. **AST Dependency Resolution & Zero Fabrication:**
   - Fixed `backend/app/ingestion/ast_parser.py` module path resolution, root stripping, and TypeScript `@/*` path aliases.
   - Extracted 120 files, 120 modules, and 369 real dependency edges from the actual NexusAct codebase with zero fabricated nodes or synthetic edges.
   - Maintained strict graph and repository isolation between `nexusact_main` (software repository) and `nexusact_fraud_demo` (synthetic financial fraud ring).

---

## 2. Architecture & Implementation Highlights

### 2.1 Backend Explanations & LLM Grounding
- `backend/app/agent/llm.py`: Enhanced `GeminiProvider` to auto-detect both `GEMINI_API_KEY` and `GOOGLE_API_KEY`, supporting `gemini-2.5-pro` and `gemini-2.5-flash` with graceful deterministic rule fallbacks when offline.
- `backend/app/agent/explanation.py`: Implemented comprehensive explanation generation supporting all 10 workspace panels with LRU caching.
- `backend/app/api/endpoints/investigation.py`: Exposed `POST /api/v1/investigation/explain-panel`.

### 2.2 Frontend Workspace & Visual Components
- `frontend/src/features/investigation/InvestigationWorkspace.tsx`: Rebuilt layout with collapsible `<aside>` vertical sidebar, category badges, and persistent DOM retention.
- `frontend/src/features/investigation/PanelExplanation.tsx`: Interactive explanation cards with provider badges (`Gemini Explanation`, `Rule-Based Grounding`, `Cached Insight`), refresh buttons, and deep accordion breakdown.
- `frontend/src/features/investigation/GraphCanvas.tsx`: Built custom SVG renderers for chip, card, diamond, circle, and pill geometries, edge midpoint label pills, stroke dash styles, and linear path layouts.

---

## 3. Automated Quality Gate Verification

All quality gates passed with zero errors:

```
[Phase 17 Quality Gate Results]
- Python Linting: ruff check backend tests       --> All checks passed (0 errors)
- Python Formatting: ruff format --check        --> 83 files cleanly formatted
- Static Type Checking: mypy backend mcp_server  --> 0 issues in 66 source files
- Backend Integration Tests: pytest -q          --> 140 passed (136 baseline + 4 Phase 17)
- Frontend Linting: oxlint                      --> 0 warnings, 0 errors in 29 files
- Frontend Tests: vitest run                    --> 20 passed across 6 test files
- Production Bundle: tsc -b && vite build        --> Built client in 1.00s (0 errors)
```

---

## 4. Key Files Changed & Created

| Path | Type | Description |
|---|---|---|
| `backend/app/agent/explanation.py` | New | Grounded multi-panel explanation service with LRU caching |
| `backend/app/agent/llm.py` | Modified | Gemini LLM provider key auto-detection and fallback |
| `backend/app/api/endpoints/investigation.py` | Modified | `POST /api/v1/investigation/explain-panel` route |
| `backend/app/ingestion/ast_parser.py` | Modified | AST module alias parsing and dependency extraction |
| `frontend/src/features/investigation/PanelExplanation.tsx` | New | Interactive Gemini/grounded explanation card component |
| `frontend/src/features/investigation/InvestigationWorkspace.tsx` | Modified | Vertical sidebar navigation and state persistence |
| `frontend/src/features/investigation/GraphCanvas.tsx` | Modified | Node SVG geometries, edge stroke dashes, midpoint labels, Path layout |
| `frontend/src/types/investigation.ts` | Modified | TypeScript interfaces for explanation requests and responses |
| `frontend/tests/phase17_workspace_and_explanations.test.tsx` | New | Vitest unit tests for PanelExplanation and workspace integration |
| `tests/integration/test_phase17_workspace_and_explanations.py` | New | Pytest integration tests for explanation API and AST parser |
| `docs/PHASE17_FINAL_REPORT.md` | New | Comprehensive engineering report for Phase 17 |
| `docs/PHASE17_ACCEPTANCE.md` | New | Verification acceptance matrix |
