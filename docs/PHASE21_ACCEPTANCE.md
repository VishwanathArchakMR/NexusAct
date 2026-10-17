# Phase 21 Acceptance Matrix: Real-Data Investigation Engine, Fraud Graph Intelligence & Visual Semantics

## Project Information
- **Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts
- **Track:** Agents That Act on Connected Data
- **Primary Database:** FalkorDB v4.4.1 (OpenCypher Engine)
- **Phase Base Commit:** `36377f4c8ff4e142b415e37264abe229b622adfc` (Phase 20 Remote Verified)
- **Phase 21 Implementation Commit:** Remote Green CI

---

## Acceptance Verification Criteria

| Category | Requirement | Implementation Artifact | Status | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Real Data Ingestion** | Dynamic delimiter sniffing, column profiling, schema mapping preview | `backend/app/finance/ingestion_engine.py`<br>`frontend/src/features/investigation/FraudInvestigationPanel.tsx` | **VERIFIED** | `preview_dataset` detects CSV/TSV/JSON, infers source/dest/amount/device/IP columns. |
| **Data Quality & Validation** | Reject invalid/malformed records (missing accounts, negative amounts, non-numeric) | `backend/app/finance/ingestion_engine.py` | **VERIFIED** | Tested in `test_validation_rejects_malformed_and_negative_rows`. 4 bad rows rejected with specific error categories. |
| **Graph Isolation** | Ingest transactions into isolated FalkorDB graph namespaces (`fin_<dataset_id>`) | `backend/app/finance/ingestion_engine.py`<br>`backend/app/finance/dataset_registry.py` | **VERIFIED** | Verified in `test_financial_ingestion_and_falkordb_isolation`. Zero mutation of `nexusact_main`. |
| **Direct Cypher Reasoning** | Multi-hop directed cycles (3-5 hops) with rotation canonicalization | `backend/app/finance/cypher_engine.py` | **VERIFIED** | Tested in `test_cycle_canonicalization` and `query_cycles` on FalkorDB. Detected 3-hop AML cycle ($28,500). |
| **Shared Infrastructure** | Graph pattern matching for shared hardware devices and IP addresses | `backend/app/finance/cypher_engine.py` | **VERIFIED** | FalkorDB `MATCH (a:Account)-[:USES_DEVICE]->(d:Device) WHERE size(accounts) > 1` finds shared `DEV_IPHONE_99`. |
| **Multi-Hop Path Tracing** | Shortest directed path traversal between accounts with edge metadata | `backend/app/finance/cypher_engine.py` | **VERIFIED** | `query_multi_hop_path` finds 2-hop directed route between `ACC_ALPHA` and `ACC_GAMMA`. |
| **Benign Controls** | Algorithmic suppression of ordinary linear transfer chains | `backend/app/finance/cypher_engine.py` | **VERIFIED** | `query_benign_controls` distinguishes `ACC_SAFE_1` and `ACC_SAFE_2` from circular transfer rings. |
| **Transparent Risk Scoring** | Mathematical decomposition of risk factors without arbitrary weights | `backend/app/finance/investigation_service.py` | **VERIFIED** | Risk score (0.0–1.0) derived from bounded contributions of circular routing (0.45), shared devices (0.25), and velocity bursts (0.15). |
| **Visual Semantics** | Persistent legend and color palette for financial and software entities | `frontend/src/features/investigation/GraphCanvas.tsx` | **VERIFIED** | Account (`#2563eb`), Transaction (`#7c3aed`), Device (`#0d9488`), IP (`#d97706`), Merchant (`#16a34a`), Module (`#6366f1`). Tested in Vitest. |
| **Context Isolation** | Codebase Git commit, repo name, and module findings isolated from Fraud tab | `frontend/src/features/investigation/InvestigationWorkspace.tsx` | **VERIFIED** | Guarded via `activeTab !== "fraud"`. Tested in `phase21_fraud_investigation.test.tsx`. |
| **Truthful State** | No synthetic hardcoded cards or prewritten findings on empty state | `frontend/src/features/investigation/FraudInvestigationPanel.tsx` | **VERIFIED** | Clear empty state prompts user to import dataset or load 1-click benchmark. |
| **Read-Only Guarantees** | Zero external funds transfer, account freeze, or state mutation | `backend/app/finance/investigation_service.py` | **VERIFIED** | Verified in `test_read_only_guarantee`. Recommends qualified human compliance review. |
| **Technical Blueprint** | Multi-tenant auth architecture & sign-up journey documentation | `docs/ACCOUNT_SIGNUP_RECOMMENDATION.md` | **VERIFIED** | Covers Clerk/Supabase auth, JWT validation, isolated tenant graphs, rate limits, zero-knowledge retention. |

---

## Test Execution Summary

- **Backend Pytest Integration Tests:** `tests/integration/test_phase21_financial_engine.py` (5/5 PASSED)
- **Frontend Vitest Unit/Integration Tests:** `frontend/tests/phase21_fraud_investigation.test.tsx` (3/3 PASSED, 23/23 total frontend tests PASSED)
- **Frontend Linter:** `oxlint` (0 warnings, 0 errors across 32 files)
- **Frontend Production Bundle:** `vite build` (Clean build, 449 kB JS)
- **Python Type Check:** `mypy backend mcp_server` (Success: 72 source files, 0 errors)
- **Python Linter & Formatter:** `ruff check` & `ruff format` (All checks passed)
