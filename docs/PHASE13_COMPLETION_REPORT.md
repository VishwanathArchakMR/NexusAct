# NexusAct — Phase 13 Completion Report: Graph-Grounded Investigations and Real Agent Capabilities

**Product:** NexusAct  
**Tagline:** Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Hackathon Track:** *Agents That Act on Connected Data*  
**Primary Graph Database:** FalkorDB v4.4.1 (Docker / Cypher / Redis Protocol)  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  
**Completion Date:** October 17, 2026  

---

## 1. Executive Summary & Mission Scope

Phase 13 delivers on the primary requirement of the hackathon: **making core agent capabilities correct, genuinely useful, evidence-backed, and demonstrable on connected graph data**.

All graph operations in NexusAct strictly execute against **FalkorDB v4.4.1**, utilizing real graph-native Cypher traversals, multi-hop path analysis, graph algorithms (PageRank), and counterfactual graph simulations (`GRAPH.COPY`).

### Key Accomplishments in Phase 13:
1. **Strict Repository-Context Invariant:** Fully resolved cross-graph leakage. Investigations strictly bind to the validated repository, graph, revision SHA, and module target. Queries asking for a module from Repo A against Repo B are rejected as structured `UNRESOLVED` without fallback substitution.
2. **Neighborhood & Paths Panel Restoration:** The panel displays the active investigation's source, intermediate nodes, target, relationship labels, and exact hop count, supplemented with 1-hop connections.
3. **Corrected Multi-Hop Semantics:** Single edges are truthfully labeled `Direct Relationship (1-hop path)`; multi-edge paths are labeled `Multi-Hop Path (N hops)`; and unconnected queries report `No path established`.
4. **OSV-Backed Dependency Security Triage:** Implemented `nexusact_security_triage` MCP tool. Inspects real manifests (`package.json`, `package-lock.json`, `requirements.txt`), queries the public OSV API, persists `PackageDependency` and `Vulnerability` nodes in FalkorDB, and traces paths to consuming internal application modules.
5. **Bounded Synthetic Fraud Investigation Demonstration:** Implemented `nexusact_investigate_fraud` MCP tool in isolated `nexusact_fraud_demo` graph. Detects rapid circular transfer rings (`acc:101 -> acc:102 -> acc:103 -> acc:101`), shared hardware device fingerprints (`dev:iphone_xyz`), and verifies benign control accounts (`acc:201`, `acc:202`) with prominent synthetic demonstration disclaimers.
6. **Google Gemini LLM Planning Adapter:** Added native structured planning using official `google-genai` SDK (`gemini-2.5-flash`), enforcing tool budgeting, strict allowlists, and deterministic heuristic fallback when unconfigured.
7. **Safe Action Proposals & FalkorDB Internal Persistence:** Issue proposals generate context-specific remediation, review, or refactoring plans. When `GITHUB_TOKEN` is unset, external execution is locked (`can_execute=false`), and users can persist the action as an internal follow-up task (`SAVED` status) in FalkorDB.
8. **Eliminated Browser Console Warnings:** Converted canvas wheel listeners to explicit native `{ passive: false }` event listeners with pointer capture cleanup.

---

## 2. Defect Reproduction & Verification Matrix

| Defect ID | Description | Root Cause | Resolution & Verification |
|---|---|---|---|
| **Defect A** | Repository-context leakage | Unregistered or mismatched repositories defaulted to primary graph | Enforced strict registry validation in `planner.py`. Returns structured `UNRESOLVED` report immediately if repository is missing or module is absent from target graph. Verified by `test_acceptance_a_repository_isolation`. |
| **Defect B** | Incomplete Neighborhood & Paths result | Component required explicit neighborhood step even when path was present | Updated `InvestigationWorkspace.tsx` to display active path nodes and relationship edges directly from completed investigation, with 1-hop fallback from subgraph. |
| **Defect C** | Generic action proposal | Single generic title regardless of investigation domain | Tailored action proposal generation across Codebase Impact, Security Triage, Synthetic Fraud Review, and Code Ownership. Added `save_internal_proposal` endpoint and UI button for FalkorDB persistence (`SAVED` state). |
| **Defect D** | Incorrect multi-hop wording | 1-hop edges labeled as "Multi-Hop Graph Path (1 hops)" | Corrected label logic: 1 hop = `Direct Relationship (1-hop path)`, $\ge 2$ hops = `Multi-Hop Path (N hops)`, 0 hops = `No path established`. Verified by `test_acceptance_c_genuine_multihop_path_distinction`. |
| **Defect E** | Browser passive event warnings | JSX `onWheel` triggered `preventDefault` inside passive listener | Implemented explicit non-passive listener via `svgRef.addEventListener("wheel", ..., { passive: false })` with cleanup in `GraphCanvas.tsx`. |

---

## 3. Real Agent Capabilities Implemented

### Capability 1: OSV-Backed Public Vulnerability Security Triage
- **MCP Tool:** `nexusact_security_triage`
- **Supported Manifests:** `package.json`, `package-lock.json`, `requirements.txt`.
- **Public API:** `https://api.osv.dev/v1/query` (with deterministic test mock handler for CI).
- **FalkorDB Schema:**
  ```cypher
  MERGE (p:PackageDependency {id: $pkg_id})
  SET p.name = $name, p.version = $version, p.ecosystem = $ecosystem
  MERGE (v:Vulnerability {id: $vuln_id})
  SET v.summary = $summary, v.severity = $severity, v.source_url = $source_url
  MERGE (p)-[:HAS_VULNERABILITY]->(v)
  ```
- **Internal Impact:** Maps vulnerable packages to consuming internal modules via `USES_PACKAGE` relationships.

### Capability 2: Bounded Synthetic Fraud Investigation Demonstration
- **MCP Tool:** `nexusact_investigate_fraud`
- **Isolated Graph:** `nexusact_fraud_demo`
- **Cypher Traversal Patterns:**
  - **Circular Transfer Ring (3 Hops):**
    ```cypher
    MATCH path = (a1:Account)-[:SENDS_TO]->(a2:Account)-[:SENDS_TO]->(a3:Account)-[:SENDS_TO]->(a1)
    WHERE a1.id = 'acc:101'
    RETURN [n IN nodes(path) | n.id] AS cycle_nodes, sum(r.amount_usd) AS volume
    ```
  - **Shared Device Infrastructure:**
    ```cypher
    MATCH (a1:Account)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(a2:Account)
    WHERE a1.id < a2.id
    RETURN a1.id, a2.id, d.id, d.model
    ```
  - **Benign Control Auditing:** Verifies `acc:201` and `acc:202` have independent hardware and normal merchant spending (`PAYS`), ensuring they are **not** flagged as fraud.
- **Truthful Labeling:** Features prominent synthetic disclaimer: *"This investigation operates strictly on synthetic, deterministic demonstration records in isolated graph 'nexusact_fraud_demo'."*

### Capability 3: Google Gemini LLM Planning Adapter
- **Provider:** `GeminiProvider` using official `google-genai` Python SDK.
- **Configuration:**
  ```bash
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=your_gemini_api_key
  GEMINI_MODEL=gemini-2.5-flash
  ```
- **Safety & Privacy:** Strict server-side tool allowlist, bounded tool budget (max 5 tools), zero exposure of private keys or full repository code to provider.
- **Fallback:** Deterministic heuristic planner activates seamlessly when credentials are absent.

### Capability 4: Contextual Actions & Safe FalkorDB Persistence
- **Action State Machine:** `PROPOSED -> SAVED | APPROVED -> SUBMITTING -> VERIFIED | FAILED | UNKNOWN`
- **Internal Persistence:** If `GITHUB_TOKEN` is unset, user can click *"Save as Internal Follow-Up Task in FalkorDB"*, transitioning the action to `SAVED` state in FalkorDB.

---

## 4. Phase 13 Acceptance Test Results

All 8 Phase 13 Acceptance Tests (`tests/integration/test_phase13_capabilities.py`) pass deterministically:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\NexusAct
collected 8 items

tests/integration/test_phase13_capabilities.py::test_acceptance_a_repository_isolation PASSED [ 12%]
tests/integration/test_phase13_capabilities.py::test_acceptance_b_codebase_graph_impact_and_id_integrity PASSED [ 25%]
tests/integration/test_phase13_capabilities.py::test_acceptance_c_genuine_multihop_path_distinction PASSED [ 37%]
tests/integration/test_phase13_capabilities.py::test_acceptance_d_mcp_tool_selection PASSED [ 50%]
tests/integration/test_phase13_capabilities.py::test_acceptance_e_security_triage_public_evidence PASSED [ 62%]
tests/integration/test_phase13_capabilities.py::test_acceptance_f_fraud_investigation_synthetic_isolation PASSED [ 75%]
tests/integration/test_phase13_capabilities.py::test_acceptance_g_action_correctness_and_safety_lock PASSED [ 87%]
tests/integration/test_phase13_capabilities.py::test_acceptance_h_failure_safety PASSED [100%]

============================== 8 passed in 4.76s ==============================
```

---

## 5. Full Quality Gate Verification

Execution of `.\scripts\check.ps1` verifies all 6 release stages:

| Stage | Command | Result | Details |
|---|---|---|---|
| **1. Python Linting & Formatting** | `ruff check .` & `ruff format --check .` | **PASS** | 0 errors across 77 Python files |
| **2. Python Type Checking** | `mypy backend mcp_server` | **PASS** | Success: no issues found in 77 source files |
| **3. Python Test Suite** | `pytest -v` | **PASS** | **109 passed** out of 109 tests (100% pass rate) |
| **4. Frontend Linting** | `oxlint` | **PASS** | 0 warnings, 0 errors on 25 frontend files |
| **5. Frontend Unit Tests** | `vitest run` | **PASS** | **13 passed** out of 13 tests |
| **6. Frontend Production Build** | `tsc -b && vite build` | **PASS** | Built in 939ms without errors or warnings |

**Quality Suite Verdict:** `ALL QUALITY CHECKS PASSED SUCCESSFULLY!`

---

## 6. Disclosures & Known Limitations

1. **Synthetic Fraud Data:** All account, transaction, and device records in `nexusact_fraud_demo` are explicitly synthetic demonstration fixtures. No live financial data is accessed.
2. **Public OSV API Rate Limits:** Public OSV queries in CI and automated testing use fast deterministic mock handlers. Live OSV queries in production may be subject to upstream Google OSV rate limits.
3. **GitHub Action Execution:** External issue creation requires a valid `GITHUB_TOKEN` and configured repository. Without tokens, NexusAct safely offers internal FalkorDB task persistence (`SAVED` status).
4. **AI-Assisted Development:** In accordance with hackathon rules, AI coding assistants (Google Antigravity IDE) were used during pair programming for test scaffolding and refactoring. System architecture, graph schemas, Cypher logic, and verification were conceived and validated by the author.
