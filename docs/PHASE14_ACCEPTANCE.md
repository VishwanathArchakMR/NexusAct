# NexusAct — Phase 14 Acceptance Specification & Verification Matrix

**Product:** NexusAct  
**Tagline:** Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Primary Database:** FalkorDB v4.4.1  
**Track:** Agents That Act on Connected Data  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  
**Document Version:** 1.0 (Phase 14 Final Boss)  

---

## 1. Acceptance Verification Matrix

| Req ID | Requirement Description | Implementation / Verification Method | Status | Limitations / Disclosure |
| :--- | :--- | :--- | :--- | :--- |
| **P14-01** | **FalkorDB Readiness & Transient LOADING Resolution** | `scripts/falkordb_probe.py` implements an authoritative Cypher probe (`RETURN 1 AS ready` on disposable probe graph). `scripts/start.ps1` retries with bounded exponential backoff across transient Redis LOADING states (AOF replay ~6.6s) without crashing PowerShell `NativeCommandError`. Tested via unit tests and live restarts. | **PASS** | Initial AOF log replay takes 6.4–6.7s on startup; probe retries bounded up to 45s. |
| **P14-02** | **Docker Health Check Optimization** | `docker-compose.yml` and `docker-compose.prod.yml` updated to require exact `PONG` response (`redis-cli ping \| grep PONG`) with 15–20s start periods, while delegating authoritative graph readiness to `scripts/falkordb_probe.py`. | **PASS** | Does not execute Cypher directly inside coarse container healthcheck. |
| **P14-03** | **Persistent WSL2 Session & Runtime Daemon** | Detached persistent keeper in `start.ps1` prevents Windows 11 idle termination of the WSL2 VM and Docker daemon. | **PASS** | Requires WSL2 on Windows when Docker Desktop native engine is offline. |
| **P14-04** | **Deterministic Setup Script (`setup.ps1`)** | Single-step `python -m uv sync --extra dev` using authoritative `pyproject.toml` containing `google-genai>=1.0.0`. Never overwrites existing user `.env`. | **PASS** | None. Safe to rerun repeatedly. |
| **P14-05** | **Codebase Graph Investigation** | Resolves modules within the selected repository's graph context, traverses reverse dependencies up to 4 hops, identifies upstream callers, scores contributor expertise, and simulates module removal on an isolated `GRAPH.COPY` clone without altering master graphs. Verified on 786-node local graph and external repos (`semantica-agi/semantica`). | **PASS** | Static AST dependencies indicate topological impact, not runtime failure proof. |
| **P14-06** | **OSV-Backed Dependency Security Triage** | Discovers declared packages in `package-lock.json`, `package.json`, `requirements.txt`. Queries public Google OSV database (`https://api.osv.dev/v1/query`). Persists `PackageDependency` and `Vulnerability` nodes in FalkorDB. Strictly respects selected repository path, does not fall back to host `Path(".")`, and reports `MANIFESTS_UNAVAILABLE` or `NO_MANIFESTS_FOUND` when files are missing. | **PASS** | Limited to 30 packages per query run to respect OSV public rate limits. |
| **P14-07** | **Bounded Synthetic Fraud Investigation** | Queries circular transfer topology (`acc:101 -> acc:102 -> acc:103 -> acc:101`) and shared device hardware clusters in isolated `nexusact_fraud_demo` graph. Audits benign controls (`acc:201`, `acc:202`) to ensure normal spending is never classified as fraud. Classifies shared infrastructure as `MEDIUM` severity risk indicator rather than proof. Includes explicit synthetic demonstration disclaimers. | **PASS** | Operates strictly on deterministic demonstration records; no real individuals. |
| **P14-08** | **LLM Planning & Tool Allowlist Guardrails** | Supports Google Gemini (`gemini-2.5-flash`) via official `google-genai` SDK and deterministic heuristic fallback when `GEMINI_API_KEY` is omitted. Validates tool names against registered allowlist, rejects unauthorized tool requests, and strictly locks target graph context so models cannot redirect queries. | **PASS** | Normal offline development uses heuristic planner without external API dependency. |
| **P14-09** | **Context-Specific Action Proposals** | Investigation reports construct tailored issue proposals for codebase refactoring, security remediation, and synthetic fraud review. Proposal includes SHA-256 payload hash and reconciliation markers. | **PASS** | Remote GitHub issue posting requires explicit `GITHUB_TOKEN`; defaults to safe internal FalkorDB `SAVED` state. |
| **P14-10** | **Graph Canvas & Dark Mode Contrast** | High-contrast tokens for all cards, inspectors, tooltips, select options, and SVG elements in both light and dark mode. SVG wheel event uses `{ passive: false }` to prevent browser warnings without breaking zoom/pan. | **PASS** | Viewport bounds display subgraphs centered on target modules. |
| **P14-11** | **Standalone Runtime Status Diagnostic (`status.ps1`)** | Inspects FalkorDB (via `falkordb_probe.py`), FastAPI (via `/ready`), and Vite (via `http://localhost:5173` with `-UseBasicParsing`). Displays clean tabular summary with log paths and exits 0 on health. | **PASS** | Standard Windows PowerShell 5.1 and PowerShell 7 compatible. |
| **P14-12** | **Automated Quality Gate & Regressions** | Full quality suite passes cleanly: Ruff check (100%), Ruff format (107 files), Mypy strict (64 files), Pytest (118/118 passing including 9 new Phase 14 regressions), Frontend Oxlint (0 errors, 0 warnings), Vitest (13/13 passing), and Vite production build (dist artifacts generated). | **PASS** | None. Complete clean pass. |

---

## 2. Test Execution Summary

### Backend Pytest Suite
- **Command:** `.\.venv\Scripts\pytest.exe -q`
- **Total Tests:** 118
- **Passed:** 118
- **Failed:** 0
- **Duration:** 44.44s
- **Coverage Areas:**
  - `tests/integration/test_phase14_regressions.py` (9 tests: LOADING classification, connection refused, live Cypher, repo isolation, unknown versions, fraud controls, LLM missing key, allowlist & graph locking, context-specific proposals)
  - `tests/integration/test_phase13_capabilities.py` (8 tests: Phase 13 acceptance suite)
  - `tests/integration/test_phase12_graph_truth_and_readiness.py` (5 tests)
  - `tests/integration/test_phase10_input_driven_gaf.py` (6 tests)
  - `tests/integration/test_phase9_public_gaf.py` (6 tests)
  - `tests/integration/test_phase8_graph_truth_and_unresolved.py` (4 tests)
  - `tests/integration/test_phase8_cors_and_connectivity.py` (4 tests)
  - `tests/integration/test_phase7_universal_connectors.py` (9 tests)
  - `tests/integration/test_phase4_real_world_sources.py` (13 tests)
  - `tests/integration/test_repository_ingestion.py` (3 tests)
  - `tests/integration/test_adaptive_agent_and_mcp.py` (5 tests)
  - `tests/integration/test_end_to_end_pipeline.py` (7 tests)
  - `tests/integration/test_github_action_safety.py` (6 tests)
  - `tests/smoke/test_falkordb_capabilities.py` (10 tests)
  - `tests/smoke/test_mcp_diagnostic.py` (2 tests)
  - `backend/tests/integration/test_readiness_api.py` (3 tests)
  - `backend/tests/unit/test_health_api.py` (4 tests)

### Frontend Quality Suite
- **Lint (Oxlint):** 0 errors, 0 warnings across 25 source files.
- **Unit & Integration (Vitest):** 13/13 tests passing across 4 test suites (`investigation.test.tsx`, `phase8_react_keys_and_ownership.test.tsx`, `phase9_universal_workspace.test.tsx`, `system_status.test.tsx`).
- **Production Build (Vite + TypeScript):** Built in 646ms with zero errors.

---

## 3. Residual Limitations & Operational Guidance

1. **Local Persistent Volume:** The FalkorDB named volume `nexusact_falkordb_data` must never be deleted with `down -v`. It preserves populated software graphs (`nexusact_main`, `repo_*`) and public knowledge graphs (`nexusact_public`).
2. **External Remote API Keys:**
   - `GEMINI_API_KEY`: Optional. When missing, NexusAct operates with 100% deterministic graph heuristic decisions.
   - `GITHUB_TOKEN`: Optional. When missing, external GitHub issues cannot be dispatched; instead, actions are safely stored as internal tasks in FalkorDB with status `SAVED`.
   - `OSV_API`: Public OSV endpoint does not require authentication; requests are rate-limited to 30 packages per query run.
