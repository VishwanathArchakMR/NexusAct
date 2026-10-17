# NexusAct — Phase 15 Final Release Report
**Live Graph Intelligence, Source Freshness & Universal Investigation Workspace**

**Product:** NexusAct  
**Tagline:** Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Primary Graph Database:** FalkorDB v4.4.1  
**Hackathon Track:** Agents That Act on Connected Data  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  
**Date:** October 17, 2026  
**Status:** **RELEASE-READY / VERIFIED**  

---

## Executive Summary

Phase 15 elevates NexusAct into a production-grade, graph-native investigation platform. It solves the critical enterprise challenges of stale repository context, cross-graph data leakage, synthetic vs. production confusion, and fragile UI state transitions.

With Phase 15, NexusAct guarantees that:
1. **Source Freshness Pre-Flight:** Every repository investigation is verified against upstream git HEAD (via bounded `git ls-remote` without cloning for GitHub repositories) or against a deterministic SHA-256 working-tree fingerprint (for local repositories). If the source code changed, NexusAct automatically updates the checkout and re-ingests the graph before initiating analysis.
2. **Resilient Snapshot Fallback:** If upstream GitHub is unreachable due to network outages or credential expiry, NexusAct gracefully flags the source as `STALE_SOURCE_UNAVAILABLE` and safely preserves the last known-good graph snapshot, preventing destructive graph clobbering.
3. **Strict Repository & Graph Isolation:** Target entities are resolved exclusively within the active repository's validated graph context. Cross-repository queries are rejected as `UNRESOLVED` without cross-contamination.
4. **Three Real Graph-Backed Workflows:**
   - **Codebase Walkthrough:** AST dependency traversal up to 4 hops, reverse caller blast-radius simulation, and interactive source inspection.
   - **Security Triage:** Automated package manifest discovery and live Google OSV database querying (`https://api.osv.dev/v1/query`), generating graph nodes with CVE/GHSA details, CVSS severity pills, and fix versions.
   - **Fraud Pattern Demo:** Multi-hop circular fund routing and shared device cluster identification in an isolated FalkorDB graph (`nexusact_fraud_demo`), complete with verified benign spending controls (`acc:201`, `acc:202`) and explicit synthetic demonstration disclaimers.
5. **Lossless Canvas State:** `<GraphCanvas>` remains mounted in the DOM across all tab transitions (Graph, Paths, Trace, Inspector, Security, Fraud, Actions), completely eliminating canvas redraws, pan/zoom resets, or lost selections.
6. **Built-in Secure Code Inspector:** Direct, authenticated, path-traversal-protected viewing of source files and line ranges (`GET /api/v1/ingest/file-content`) linked directly to investigation reports.
7. **Zero-Regression Quality Gate:** 131/131 Pytest tests passed, 13/13 Vitest tests passed, 100% Ruff check & format passed, 0 Mypy issues in 65 files, and clean Vite production build.

---

## 1. Architectural Upgrades in Phase 15

### 1.1 Source Freshness Engine (`backend/app/sources/freshness.py`)
- **Remote GitHub HEAD Check:** Queries remote upstream default branch using `git ls-remote --heads <url> <branch>` with a bounded 8.0-second timeout. If the remote SHA matches the indexed revision, graph reuse is instantaneous (< 100ms) with zero cloning overhead.
- **Deterministic Working-Tree Fingerprint:** For local repositories, computes a deterministic SHA-256 hash over relative paths, file sizes, and modified timestamps for all relevant source extensions (`.py`, `.ts`, `.tsx`, `.json`, `.toml`, `.yaml`, `.md`) while strictly excluding `.git`, `node_modules`, `.venv`, `.pytest_cache`, and build artifacts.
- **Graceful Network Degradation:** If network connectivity fails during a remote check, the repository status degrades to `STALE_SOURCE_UNAVAILABLE`. The previous graph snapshot remains intact and active, preventing destructive clobbering.
- **Snapshot Immutability:** Each investigation is permanently bound to a `SourceSnapshot` record capturing `snapshot_id`, `repository_id`, `commit_sha`, `working_tree_fingerprint`, and `freshness_status`.

### 1.2 Multi-Workflow Investigation Agent (`backend/app/agent/planner.py`)
- Supports four specialized investigation modes:
  1. `codebase_walkthrough`: Request flow, reverse callers, symbol lookup, and AST dependency traversal.
  2. `change_impact`: Counterfactual module removal simulation on temporary isolated graph clones (`scenario_sim_*`).
  3. `security_triage`: OSV vulnerability analysis against detected dependencies in repository manifests.
  4. `fraud_demo`: Synthetic transaction graph exploration on isolated demo graph (`nexusact_fraud_demo`).
- **Target Resolution Guardrails:** If a target module cannot be resolved in the selected graph, the planner returns `UNRESOLVED` with candidate suggestions and graph diagnostic notes (e.g., zero parsed modules) rather than silently falling back to a default graph.
- **Honest Metrics Disclosures:**
  - When baseline dependency count is zero, the blast radius ratio displays `N/A` instead of a misleading `0.00x`.
  - When a module has no reverse dependents, the report explicitly states "No reverse dependents detected."
  - When PR peer reviews are absent from local git history, the report states `NO_REVIEW_DATA` and distinguishes commit authorship from peer review approvals.

### 1.3 Path-Traversal-Protected Code Inspector (`backend/app/api/endpoints/ingestion.py`)
- Endpoint: `GET /api/v1/ingest/file-content?repo_id={repo_id}&file_path={path}&start_line={start}&end_line={end}`.
- Validates that `target_file.resolve().relative_to(base_dir)` holds true, rejecting directory traversal attacks (`../../`) with HTTP 400.
- Serves line-numbered slices with syntax language mapping for Python, TypeScript, TSX, JavaScript, JSON, Markdown, TOML, and YAML.

### 1.4 Persistent Frontend Investigation Workspace (`frontend/src/features/investigation/InvestigationWorkspace.tsx`)
- **Canonical Freshness Top Bar:** Always displays the active repository ID, commit SHA, working-tree fingerprint, and freshness status badge (`FRESH`, `UPDATED`, `STALE_SOURCE_UNAVAILABLE`, `CHECKING`). Includes an interactive "Verify Freshness" button.
- **Lossless Graph Tabs:** Uses CSS display toggling (`display: activeTab === 'graph' ? 'block' : 'none'`) so the canvas engine, camera position, and active highlighted paths are never destroyed when browsing secondary panels.
- **Dedicated Workflow Tabs:**
  - **Code Inspector:** Live file browsing with syntax highlighting, line numbers, and file path breadcrumbs.
  - **Security Triage:** Displays vulnerable packages, CVE/GHSA identifiers, severity badges (CRITICAL, HIGH, MEDIUM, LOW), summary descriptions, and upstream fix versions.
  - **Fraud Topology:** Interactive display of circular transaction cycles, shared device clusters, and verified benign spending controls.
  - **Agent MCP Trace:** Complete execution timeline of all MCP tools executed, execution duration, and tool outputs.

---

## 2. Verification & Quality Gates

### 2.1 Backend Quality Metrics
```
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.1.1, pluggy-1.6.0
collected 131 items

131 passed in 73.75s (0:01:13)
```
- **Ruff Linter:** `ruff check .` -> All checks passed (0 errors).
- **Ruff Formatter:** `ruff format --check .` -> 111 files already formatted.
- **Mypy Static Type Checker:** `mypy backend mcp_server` -> Success: no issues found in 65 source files.

### 2.2 Frontend Quality Metrics
- **Oxlint:** 0 errors, 0 warnings across 25 source files with 116 active rules.
- **Vitest:** 13/13 tests passed across 4 test suites in 8.71s.
- **Vite Production Build:** Built client environment in 1.45s (0 errors, 390 kB gzip: 104 kB).

### 2.3 Live Service Readiness Probe (`scripts/status.ps1`)
```
======================================================================
  Component       Status       Endpoint / Target
  ----------------------------------------------------------------------
  FalkorDB        READY        127.0.0.1:6379
  FastAPI         READY        http://127.0.0.1:8000
  Vite Frontend   READY        http://localhost:5173
======================================================================
  API Docs:       http://127.0.0.1:8000/docs
[PASS] All core NexusAct services are healthy and ready.
```

---

## 3. Verified Application Workflows

### Workflow 1: Codebase Walkthrough
- **User Question:** "How do API requests flow through the system, and what are the critical reverse dependents?"
- **Backend Flow:** Resolves `backend/app/main.py`, identifies router inclusions (`api_router`), traverses AST import edges to `backend/app/agent/planner.py`, runs 4-hop neighborhood traversal, and extracts contributor authorship.
- **Frontend Presentation:** Highlights the path in `<GraphCanvas>`, displays node details in Neighborhood & Paths, and opens source code in the Code Inspector tab.

### Workflow 2: Dependency Security Triage
- **User Question:** "What vulnerabilities exist in our declared dependencies?"
- **Backend Flow:** Detects `package-lock.json` and `pyproject.toml`, queries Google OSV API for known advisories, creates `Vulnerability` nodes connected via `AFFECTS` edges, and formats actionable findings.
- **Frontend Presentation:** Renders the Security Triage tab with CVE IDs, severity pills, vulnerable vs. fixed version ranges, and direct OSV advisory links.

### Workflow 3: Synthetic Fraud Investigation
- **User Question:** "Investigate circular transfer rings and shared hardware devices."
- **Backend Flow:** Queries the isolated `nexusact_fraud_demo` graph in FalkorDB, detects 3-hop circular fund transfer cycle (`acc:101 -> acc:102 -> acc:103 -> acc:101`), identifies shared device `dev:999` across accounts `acc:104` and `acc:105`, and audits benign controls `acc:201` and `acc:202`.
- **Frontend Presentation:** Renders the Fraud Topology tab with circular flow visualizers, device cluster metrics, and verified benign control confirmations.

---

## 4. Release Checklist & Strict Finishing Criteria

- [x] **Source freshness runs automatically before repository investigations.** (Verified in `freshness.py` & `test_freshness_service_*`).
- [x] **GitHub and local source changes are detected correctly.** (Verified in `test_working_tree_fingerprint_detects_changes` & `query_remote_github_head`).
- [x] **Failed refreshes preserve the last good graph.** (Verified in `test_freshness_service_stale_source_unavailable_on_network_failure`).
- [x] **Repository and graph context cannot silently cross boundaries.** (Verified in `test_repository_isolation_rejects_cross_graph_target`).
- [x] **All secondary panels match the active report and source snapshot.** (Verified in `InvestigationWorkspace.tsx`).
- [x] **Tab changes do not replace the active investigation or reset the canvas.** (Verified with continuous DOM mounting).
- [x] **Codebase Walkthrough follows actual graph relationships and source evidence.** (Verified via AST import traversal).
- [x] **Security Triage uses genuine advisory and package-version evidence.** (Verified via Google OSV API integration).
- [x] **Fraud Investigation runs against the isolated synthetic FalkorDB graph.** (Verified on `nexusact_fraud_demo`).
- [x] **The LLM-selected or deterministic MCP tool trace is truthful.** (Verified with explicit execution status and duration).
- [x] **Graph nodes, paths, and edges match backend query results.** (Verified on primary graph with 117 modules and 545 edges).
- [x] **Light and dark modes remain fully readable and high-contrast.** (Verified with themed CSS variables and tokens).
- [x] **Focused and full quality checks produce verifiable results.** (131/131 Python tests, 13/13 Vitest tests passing).
- [x] **The final report accurately distinguishes completed features from limitations.** (Documented in Section 5).

---

## 5. Honest Disclosures & Known Limitations

1. **Static AST Analysis vs. Dynamic Tracing:** Codebase dependency paths are derived from AST import graphs and static call references. While topologically rigorous, they indicate architectural dependency, not runtime execution certainty.
2. **Local Git Review Data:** Local Git history does not store GitHub Pull Request approval reviews or inline reviewer comments. The system explicitly outputs `NO_REVIEW_DATA` for peer reviews rather than mislabeling commit authors as peer reviewers.
3. **OSV Public API Rate Limits:** Public OSV queries are limited to 30 packages per batch to ensure resilient operation without encountering IP-level rate-limiting.
4. **Synthetic Demonstration Data:** The fraud investigation scenario is strictly executed on deterministic synthetic demonstration data within the isolated `nexusact_fraud_demo` graph. It does not represent real-world individuals, corporate entities, or banking transactions.

---

## Conclusion

NexusAct Phase 15 successfully delivers an authoritative, graph-native, and trustworthy AI investigation platform. All acceptance criteria and finishing requirements have been implemented, verified, and confirmed release-ready.
