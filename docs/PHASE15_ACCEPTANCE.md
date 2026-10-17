# NexusAct — Phase 15 Acceptance Specification & Verification Matrix

**Product:** NexusAct  
**Tagline:** Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Primary Database:** FalkorDB v4.4.1  
**Track:** Agents That Act on Connected Data  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  
**Document Version:** 1.0 (Phase 15 Live Graph Intelligence & Investigation Workspace)  

---

## 1. Acceptance Verification Matrix

| Req ID | Requirement Description | Implementation / Verification Method | Status | Limitations / Disclosure |
| :--- | :--- | :--- | :--- | :--- |
| **P15-01** | **Authoritative Source Freshness Validation** | `backend/app/sources/freshness.py` implements `SourceFreshnessService.check_and_refresh_source()`. Prior to any repository-backed investigation, upstream revision is checked via bounded `git ls-remote` without cloning (for remote GitHub repos) or via deterministic working-tree fingerprinting (for local repos). Ingestion re-runs only if code changed. Tested in `test_phase15_live_intelligence.py`. | **PASS** | Bounded `git ls-remote` timeout is 8.0s; local fingerprint scans `.py`, `.ts`, `.tsx`, `.json`, `.toml` while strictly ignoring `.git`, `node_modules`, `.venv`, and build artifacts. |
| **P15-02** | **Last-Good Snapshot Preservation on Network Outage** | When remote GitHub HEAD queries encounter network timeouts, DNS errors, or rate limits, the service gracefully degrades to `STALE_SOURCE_UNAVAILABLE`. The last known-good graph snapshot is preserved and activated with truthful metadata rather than destroying existing graph data. | **PASS** | Stale status is prominently flagged in UI and logged under `known_gaps`. |
| **P15-03** | **Multi-Repository & Graph Context Isolation** | Backend binds every investigation report to validated repository metadata and target graph. MCP tools execute strictly within the active graph. Cross-graph module queries (e.g. querying a module that exists only in another repo) are rejected as `UNRESOLVED` without cross-contamination. Consecutive multi-graph test runs verified in `test_consecutive_investigations_across_three_distinct_graphs`. | **PASS** | Module autocompletion and queries strictly scope to the active graph name. |
| **P15-04** | **Codebase Walkthrough Investigation Workflow** | First of 3 core live workflows. Traces API request flows, AST reverse import paths up to 4 hops, identifies central entry points, and scores contributor authorship. Links graph nodes directly to live source lines. | **PASS** | Static AST imports reflect topological dependency graph, not runtime call-stack proof. |
| **P15-05** | **Live Dependency Security Triage Workflow** | Second core live workflow. Discovers declared dependencies (`package.json`, `requirements.txt`), queries Google's public OSV database (`https://api.osv.dev/v1/query`), creates graph relationships, and presents CVE/GHSA advisory details, severity pills, and fix versions. Truthfully handles `MANIFESTS_UNAVAILABLE` or clean dependencies. | **PASS** | Public OSV query rate-limited to 30 packages per batch to ensure stability. |
| **P15-06** | **Synthetic Fraud Ring Investigation Workflow** | Third core live workflow. Queries isolated FalkorDB graph (`nexusact_fraud_demo`) for circular fund cycles (`acc:101 -> acc:102 -> acc:103 -> acc:101`) and shared device hardware clusters. Audits benign controls (`acc:201`, `acc:202`) to ensure legitimate transactions are never flagged. Highlights synthetic disclaimer throughout. | **PASS** | Operates strictly on deterministic synthetic demonstration data; no real individuals or banking accounts. |
| **P15-07** | **Secure In-Workspace Code Inspector** | Implemented `GET /api/v1/ingest/file-content` with strict canonical path traversal checks (`target_file.relative_to(base_dir)`). Allows interactive viewing of source files and line ranges linked from investigation reports. | **PASS** | Path traversal attacks (`../`) are blocked with HTTP 400. File access strictly scoped to repository root. |
| **P15-08** | **Lossless Canvas State Across Tab Transitions** | `frontend/src/features/investigation/InvestigationWorkspace.tsx` mounts `<GraphCanvas>` continuously, toggling visibility via CSS display (`activeTab === 'graph' ? 'block' : 'none'`). Moving between Graph, Paths, Trace, Inspector, Security, Fraud, and Actions preserves pan, zoom, selection, and active path highlights without reset. | **PASS** | Viewport resets only when initiating a fresh investigation or switching repositories. |
| **P15-09** | **Truthful Disclosures & Honest Metrics** | Reports display `N/A` for blast radius ratio when baseline dependency count is zero (eliminating false `0.00x` claims); explicit disclosures when a module has zero reverse dependents; explicit `NO_REVIEW_DATA` separating git commit authorship from peer PR reviews. | **PASS** | Eliminates speculative or fabricated risk assessments. |
| **P15-10** | **Comprehensive Full Quality Gate** | All quality checks pass with 0 errors: Python Ruff check (100%), Ruff format (111 files), Mypy strict (65 files), Pytest (131/131 passing including 13 new Phase 15 live tests), Frontend Oxlint (0 errors, 0 warnings across 25 files), Vitest (13/13 passing), and Vite production build (clean bundle in 1.45s). | **PASS** | Zero test skips, zero weakened assertions, zero regressions. |

---

## 2. Test Execution Summary

### Backend Pytest Suite
- **Command:** `.\.venv\Scripts\pytest.exe -q`
- **Total Tests:** 131
- **Passed:** 131
- **Failed:** 0
- **Duration:** 73.75s
- **Phase 15 Focused Suite:** `tests/integration/test_phase15_live_intelligence.py` (13 tests)
  1. `test_working_tree_fingerprint_deterministic` (PASSED)
  2. `test_working_tree_fingerprint_detects_changes` (PASSED)
  3. `test_query_remote_github_head_success` (PASSED)
  4. `test_freshness_service_stale_source_unavailable_on_network_failure` (PASSED)
  5. `test_consecutive_investigations_maintain_snapshot_consistency` (PASSED)
  6. `test_repository_isolation_rejects_cross_graph_target` (PASSED)
  7. `test_consecutive_investigations_across_three_distinct_graphs` (PASSED)
  8. `test_investigation_blast_radius_na_when_zero_baseline` (PASSED)
  9. `test_investigation_reviewer_distinguishes_commit_authors_from_reviews` (PASSED)
  10. `test_security_triage_osv_live_or_clean` (PASSED)
  11. `test_fraud_demo_circular_flow_and_benign_controls` (PASSED)
  12. `test_file_content_endpoint_reads_source` (PASSED)
  13. `test_file_content_endpoint_blocks_path_traversal` (PASSED)

### Static Analysis & Type Checking
- **Ruff Check:** `.\.venv\Scripts\ruff.exe check .` -> All checks passed!
- **Ruff Format Check:** `.\.venv\Scripts\ruff.exe format --check .` -> 111 files already formatted.
- **Mypy Type Checking:** `.\.venv\Scripts\mypy.exe backend mcp_server` -> Success: no issues found in 65 source files.

### Frontend Quality Suite
- **Oxlint:** `npm.cmd run lint` -> Found 0 warnings and 0 errors across 25 files with 116 rules.
- **Vitest:** `npm.cmd test -- --run` -> 4 test files passed, 13/13 tests passed (8.71s).
- **Vite Production Build:** `npm.cmd run build` -> Clean bundle built in 1.45s (0 errors).

---

## 3. Live Service Verification Matrix

| Service | Target / Port | Readiness Probe | Live Verification Result |
| :--- | :--- | :--- | :--- |
| **FalkorDB** | `127.0.0.1:6379` | `scripts/falkordb_probe.py` | Operational; primary graph `nexusact_main` (117 modules, 545 edges) and demo graph `nexusact_fraud_demo` responsive |
| **FastAPI Backend** | `http://127.0.0.1:8000` | `GET /ready` & `GET /health` | HTTP 200 OK, `app_status: READY`, all routes mounted |
| **Vite Dev Server** | `http://localhost:5173` | `GET /` | HTTP 200 OK, single-page application responding |
