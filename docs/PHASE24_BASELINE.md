# Phase 24 Baseline Audit & Runtime Incident Report

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Competition Track:** Agents That Act on Connected Data  
**Primary Database:** FalkorDB v4.4.1  
**Baseline Commit:** `5475c03b9f8f9752c8863816c1557ac4f38b273d`  
**Date:** 2026-10-18  

---

## 1. Incident Summary & Observed Symptoms

During runtime verification of the Phase 23 release on a live deployment (`http://localhost:5173` connecting to `http://127.0.0.1:8000`), the following critical issues were reproduced in the browser console and network tab:

1. **404 Not Found on Graph AI Chat (`/api/v1/investigation/chat`):**
   - **Observed Error:** The right-side assistant drawer submitted queries to `POST /api/v1/investigation/chat` and received HTTP 404 Not Found. The UI rendered `"Investigation Failed: Not Found"`.
   - **Root Cause:** A long-running uvicorn daemon process (task-11295) was launched prior to Phase 23 and kept running in the background without auto-reload. Consequently, the newly added chat service and endpoint routes were missing from the active server in memory. Additionally, the backend router structure in `backend/app/api/endpoints/investigation.py` lacked a standard router `prefix="/investigation"` declaration, leading to dual alias route decorators (`@router.post("/investigation/chat")` and `@router.post("/chat", include_in_schema=False)`).

2. **Scenario Simulation Had No Candidate Modules:**
   - **Observed Error:** The simulation panel reported `"No candidate modules in graph"` and disabled the "Run Counterfactual Simulation" button.
   - **Root Cause:** The browser requested `GET /api/v1/investigation/simulation-candidates`, which failed with HTTP 404 on the stale backend. Furthermore, when selecting an onboarded GitHub repository like `repo:vishwanatharchakmr_aletheiaos`, the graph name resolution did not default cleanly if the repository had not yet completed full AST ingestion.

3. **Reviewers & Authors 404:**
   - **Observed Error:** Requests to `GET /api/v1/investigation/reviewers` failed with HTTP 404 Not Found.
   - **Root Cause:** The endpoint was registered in code but not loaded in the running backend process.

4. **Code Inspector 404 on Cross-Repository Navigation:**
   - **Observed Error:** `GET /api/v1/ingest/file-content?repo_id=repo:vishwanatharchakmr_aletheiaos&file_path=frontend/src/app.py` returned HTTP 404.
   - **Root Cause:** In `CodeInspector.tsx`, when an active target node `mod:frontend.src.app` was selected, the component naively generated a file path by appending `.py` (`frontend/src/app.py`), even though the repository is TypeScript/React (`frontend/src/App.tsx`). The backend's `get_file_content` endpoint did not resolve module paths from the FalkorDB graph (`m.path`), resulting in a hard 404 file not found error.

5. **Fraud Dashboard Dataset Dropdown Displayed Repeated `(txs)` Labels and Unclear Provenance:**
   - **Observed Error:** The financial dataset dropdown displayed all entries as ` (txs)` without distinguishable dataset names or record counts, and the badge displayed `"Unlabeled"`.
   - **Root Cause:** Schema field mismatch between FastAPI backend model `FinancialDatasetMetadata` and frontend TypeScript interface:
     - Backend serialized: `name`, `total_rows`, `accounts_count`, `has_ground_truth`, `data_provenance_note`.
     - Frontend expected: `dataset_name`, `record_count`, `account_count`, `has_ground_truth_labels`, `provenance_note`.
     - Because the fields were undefined in the JSON received by the frontend, `{d.dataset_name} ({d.record_count} txs)` evaluated to `undefined (undefined txs)`, rendering as ` (txs)`.

---

## 2. API Contract & Route Mismatch Inventory

| Frontend Request URL | Expected HTTP Method | Backend Registered Route | Status Before Phase 24 | Resolution Required |
|---|:---:|---|:---:|---|
| `/api/v1/investigation/chat` | `POST` | Dual aliases (`/investigation/chat` & `/chat`) | 404 on stale server | Standardize router `prefix="/investigation"` |
| `/api/v1/investigation/simulation-candidates` | `GET` | Dual aliases (`/investigation/simulation-candidates` & `/simulation-candidates`) | 404 on stale server | Standardize on `/investigation/simulation-candidates` |
| `/api/v1/investigation/simulate` | `POST` | Dual aliases (`/investigation/simulate` & `/simulate`) | 404 on stale server | Standardize on `/investigation/simulate` |
| `/api/v1/investigation/reviewers` | `GET` | Dual aliases (`/investigation/reviewers` & `/reviewers`) | 404 on stale server | Standardize on `/investigation/reviewers` |
| `/api/v1/investigation/explain-panel` | `POST` | `/api/v1/investigation/explain-panel` | 200 | Retain on `/investigation/explain-panel` |
| `/api/v1/investigation/recent` | `GET` | `/api/v1/investigation/recent` | 200 | Retain on `/investigation/recent` |
| `/api/v1/investigate` | `POST` | `/api/v1/investigate` | 200 | Maintain compatibility with `/api/v1/investigate` |
| `/api/v1/ingest/file-content` | `GET` | `/api/v1/ingest/file-content` | 404 on synthetic/extension mismatch | Resolve module file paths from FalkorDB `m.path` |
| `/api/v1/finance/datasets` | `GET` | `/api/v1/finance/datasets` | 200 with schema mismatch | Align Pydantic and TypeScript metadata fields |

---

## 3. Database & Graph State Inspection

FalkorDB v4.4.1 is verified running on `127.0.0.1:6379`.
Active graphs in FalkorDB:
- `nexusact_main`: 140 files, 45 modules, 33 commits, 1 author (`Vishwanath Archak M R`).
- `fin_aml_synthetic_be_cdbfbf`: 20 transaction records, 8 accounts, isolated financial graph.
- `repo_vishwanatharchakmr_alethe`: 25 modules, 36 dependency edges, 1 commit.

---

## 4. Phase 24 Action Plan

1. **Contract Alignment:**
   - Declare `investigation.router = APIRouter(prefix="/investigation")`.
   - Remove duplicate `include_in_schema=False` alias decorators.
   - Maintain top-level `/api/v1/investigate` and `/api/v1/tools/*` endpoints.
   - Add automated test `tests/integration/test_route_contracts.py` ensuring every frontend API route exists in FastAPI's OpenAPI schema.
2. **Financial Metadata & Provenance Repair:**
   - Update `FinancialDatasetMetadata` in `backend/app/finance/models.py` with both canonical and alias fields (`dataset_name`, `record_count`, `account_count`, `has_ground_truth_labels`, `provenance_note`).
   - Update `FraudInvestigationPanel.tsx` with unambiguous dropdown labels and full provenance details.
3. **Source Inspection & Code Inspector Repair:**
   - In `backend/app/api/endpoints/ingestion.py`, resolve `file_path` via `m.path` if direct file lookup fails.
   - In `frontend/src/features/investigation/CodeInspector.tsx`, fall back gracefully when a file is missing.
4. **Chat Drawer Refinement:**
   - Ensure right-side fixed positioning does not clip when browser DevTools are open.
   - Accurately report LLM configuration status.
5. **Quality Gates & End-to-End Verification:**
   - Verify full pytest (162+ tests), vitest (26+ tests), ruff, mypy, oxlint, and live browser flow.
