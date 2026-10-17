# NexusAct — Phase 20 Acceptance & Verification Matrix

**Product:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Track:** Agents That Act on Connected Data  
**Primary Database:** FalkorDB v4.4.1  
**Base Commit:** `67f7a7f`  

---

## 1. Acceptance Requirements & Verification Status

| Requirement | Phase 20 Verification Method | Current Status | Blockers |
|---|---|---|---|
| **1. Persistent Vertical Navigation** | Verify Software Graph sidebar sections: Explore (Graph Explorer, Code Inspector), Analyze (Scenario Simulation, Reviewers & Authors, Agent MCP Trace, Neighborhood & Paths), Evidence & Action (Source Provenance, Verified Action), Workflows (Security Triage, Fraud Topology). Ensure active investigation ID survives navigation. | ✅ PASS | None |
| **2. Two Graph Views** | Verify `GraphCanvas.tsx` toggle: *Investigation Path* (linear directed flow of verified hops) vs *Network Overview* (hierarchical lane layout: callers left, target center, dependencies right). Zoom, pan, fit-to-view, node dragging, search, filters. | ✅ PASS | None |
| **3. Grounded Panel Explanations** | Verify `PanelExplanation` across all 10 panels (`graph`, `code`, `simulation`, `reviewers`, `trace`, `neighborhood`, `provenance`, `action`, `security`, `fraud`). Check structured fields (takeaway, what looking at, findings, why matters, evidence list, limitations, next step). In-memory LRU cache with SHA-256 hash key. | ✅ PASS | None |
| **4. Truthful Gemini & Fallback Disclosures** | Verify provider status disclosures (`GEMINI_ACTIVE`, `FALLBACK_ACTIVE`, `NOT_CONFIGURED`). Never claim LLM generated results when deterministic engine executed. Safe API key redaction (`[REDACTED]`). Safe connectivity test endpoint `/api/v1/system/llm-test`. | ✅ PASS | None |
| **5. Genuine Multi-Hop Path Reasoning** | Query FalkorDB shortest path for real $\ge 2$-hop path: `backend.app.api.router` $\rightarrow$ `backend.app.api.endpoints.investigation` $\rightarrow$ `backend.app.graph.client`. Verify edge directions, intermediate nodes, AST provenance, and path highlight in canvas. | ✅ PASS | None |
| **6. Real Codebase Walkthrough** | Pin source snapshot to commit SHA. Trace imports, open exact source lines in Code Inspector, outline classes/functions, distinguish static AST import from verified runtime invocation. | ✅ PASS | None |
| **7. Real Security Triage (OSV)** | Manifest inspection (`package-lock.json`, `requirements.txt`), live OSV API query (`https://api.osv.dev/v1/query`), internal reachability traversal, explicit disclosure of zero known advisories vs simulated test fixtures. | ✅ PASS | None |
| **8. Isolated Synthetic Fraud Investigation** | Isolated graph `nexusact_fraud_demo`. Multi-hop circular transfer ring (depth 3, $27,700), shared infrastructure (`dev:iphone_xyz`), benign retail controls (`acc:201`, `acc:202`). Clear synthetic disclaimers. | ✅ PASS | None |
| **9. Action Proposals & Cryptographic Memory** | State machine: `PROPOSED` $\rightarrow$ `SAVED` $\rightarrow$ `APPROVED` $\rightarrow$ `SUBMITTING` $\rightarrow$ `VERIFIED`. SHA-256 payload hash binding. Human-in-the-loop approval gate for GitHub issue creation. Preservation of investigation state on reload. | ✅ PASS | None |
| **10. Judge Access & Deployment Readiness** | Multi-tenant graph-per-repository isolation in FalkorDB. Protected system graphs. Dedicated demo mode. Evaluated zero-cost deployment options (Local Docker Compose, FalkorDB Cloud + Render/Railway/Fly.io). | ✅ PASS | None |
| **11. Automated Quality Gates** | Verify: Ruff lint (0 errors), Ruff format (clean), Mypy (0 errors on `backend` & `mcp_server`), Pytest (146+ passing), Frontend lint (0 errors), Vitest (20 passing), Vite build (clean bundle). | ✅ PASS | None |
| **12. Reproducible Documentation & Demo Script** | Update `README.md`, `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION_CHECKLIST.md`, and author `docs/PHASE20_FINAL_REPORT.md`. | ✅ PASS | None |

---

## 2. Verification Command Log

```powershell
# 1. Backend Lint & Format
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .

# 2. Backend Type Check
.\.venv\Scripts\mypy.exe backend mcp_server

# 3. Backend Test Suite
.\.venv\Scripts\pytest.exe -q

# 4. Frontend Lint, Tests, and Build
Push-Location frontend
npm.cmd run lint
npm.cmd test -- --run
npm.cmd run build
Pop-Location
```

---

## 3. Conclusion

All acceptance criteria for Phase 20 are satisfied and verified against the running application and live FalkorDB instance.
