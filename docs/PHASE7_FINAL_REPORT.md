# NexusAct — Phase 7 Final Product Completion & Release Report

**Product:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  
**Primary Graph Database:** FalkorDB v4.4.1  
**Status:** COMPLETE & RELEASE READY  

---

## 1. Executive Summary & Mission Fulfillment

Phase 7 successfully achieved both mandatory objectives:
1. **Critical Local Runtime Recovery:** Conclusively diagnosed and resolved the root cause of the `ERR_CONNECTION_REFUSED` / localhost:8000 connection refusal. Hardened startup orchestration (`scripts/start.ps1`, `scripts/stop.ps1`) to reliably manage WSL2 Docker lifecycle, persistent FalkorDB availability, and background FastAPI/Uvicorn processes with standard log redirection.
2. **Universal GraphAction Fabric (GAF):** Expanded NexusAct from a pure software repository intelligence agent into an evidence-grounded, universal public-data discovery architecture. Implemented four approved read-only connectors (Hugging Face Hub, OpenAlex, Crossref, and Wikidata), deterministic entity & relationship modeling in FalkorDB, and the **Universal Ask GAF** natural-language investigation planner.
3. **Quality & CI Remediation:** Repaired the GitHub Actions CI workflow timing failure by inserting an explicit Cypher module probe (`RETURN 1`) before pytest execution. All quality checks (Ruff check, Ruff format, Mypy type-checking, 74 Pytest integration tests, Oxlint, Vitest, and Vite production bundle build) pass cleanly.

---

## 2. Root Cause Analysis & Local Runtime Fix

### 2.1 Why `localhost:8000` Failed Initially (`ERR_CONNECTION_REFUSED`)
1. **WSL2 Distro Termination:** On Windows systems running Docker inside WSL2 without Docker Desktop, WSL2 automatically suspends or terminates the Ubuntu distribution after ~15 seconds of process inactivity. This abruptly killed the background Docker daemon and closed port 6379 for FalkorDB.
2. **PowerShell `Start-Job` Scope Cleanup:** The existing `scripts/start.ps1` used PowerShell `Start-Job` for launching Uvicorn. In PowerShell, jobs created by `Start-Job` are bound to the host session; as soon as the startup script or terminal session exited, the background job was terminated.
3. **CORS Origins:** Handled correctly in `backend/app/core/config.py` with explicit allowed origins (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000`). The initial failure was pure connection refusal (no process listening), not a CORS error.

### 2.2 Fix Implemented
- **Auto-Starting WSL2 Docker:** Updated `scripts/start.ps1` to detect whether `dockerd` is active; if stopped, it automatically starts `service docker start` and launches a lightweight keepalive process (`Start-Process wsl -ArgumentList "..." -WindowStyle Hidden`).
- **Detached Background Processes:** Replaced `Start-Job` with `Start-Process` running `.venv\Scripts\python.exe -m uvicorn backend.app.main:app` and redirecting `stdout` and `stderr` to `logs/backend.log` and `logs/backend.err.log`.
- **Accurate Readiness Verification:** Implemented bounded polling of `http://127.0.0.1:8000/health` and Cypher queries against FalkorDB before announcing readiness.
- **Clean Shutdown:** Updated `scripts/stop.ps1` with `Get-CimInstance Win32_Process` to terminate orphaned Uvicorn and Vite processes without deleting persistent FalkorDB volumes.

---

## 3. GitHub Actions CI Failure Diagnosis & Resolution

### 3.1 Failure Details
- **Failed Run:** [GitHub Actions Run 38862013566](https://github.com/VishwanathArchakMR/NexusAct/actions/runs/38862013566)
- **Job ID:** `116846208577` (Backend Quality Gate)
- **Root Cause:** In GitHub Actions service containers, `options: --health-cmd "redis-cli ping"` reports healthy as soon as Redis TCP socket is listening. However, FalkorDB requires an additional 3–6 seconds to initialize its internal Cypher module and graph engine. When Pytest started immediately after TCP ping, the first graph initialization query failed with a connection/module initialization exception.

### 3.2 Resolution in `.github/workflows/ci.yml`
- Increased health check retries and reduced interval (`--health-retries 10 --health-interval 5s`).
- Inserted an explicit **FalkorDB module readiness wait step** in the CI pipeline prior to Pytest:
  ```yaml
  - name: Wait for FalkorDB module readiness
    run: |
      python - <<'EOF'
      import sys, time, falkordb
      deadline = time.monotonic() + 45
      while time.monotonic() < deadline:
          try:
              db = falkordb.FalkorDB(host="127.0.0.1", port=6379)
              db.connection.ping()
              g = db.select_graph("_ci_probe")
              g.query("RETURN 1")
              print("FalkorDB module is ready.")
              sys.exit(0)
          except Exception as e:
              time.sleep(3)
      sys.exit(1)
      EOF
  ```

---

## 4. Universal GraphAction Fabric (GAF) Architecture

### 4.1 Approved Source Connector Registry (`backend/app/sources/connector_registry.py`)
- Extensible, typed connector registry ensuring all outbound calls use **fixed class constants** as API base URLs.
- Arbitrary user-controlled URLs are strictly prohibited.
- Bounded pagination, rate limiting (inter-request minimum intervals), and response size limits (512 KB max).

| Connector | Source ID | API Base (Constant) | Entity Types | Supported Relationships |
|---|---|---|---|---|
| **Hugging Face Hub** | `huggingface` | `https://huggingface.co/api/` | Model, Dataset | `CREATED_BY`, `USES_DATASET`, `HOSTED_ON` |
| **OpenAlex** | `openalex` | `https://api.openalex.org/` | Paper, Person, Organization, Topic | `AUTHORED`, `AFFILIATED_WITH`, `CITES`, `HAS_TOPIC` |
| **Crossref REST** | `crossref` | `https://api.crossref.org/` | Paper, Person, Organization | `AUTHORED`, `AFFILIATED_WITH`, `CITES`, `FUNDED_BY` |
| **Wikidata Action** | `wikidata` | `https://www.wikidata.org/w/api.php` | Organization, Person, Topic, Model | `AFFILIATED_WITH`, `CREATED_BY`, `HAS_TOPIC` |

### 4.2 Data Normalization & Graph Model
- **Namespaced Identifiers:** `<source_id>:<external_id>` (e.g. `huggingface:meta-llama/Llama-3-8B`, `openalex:W2741809807`, `wikidata:Q92764`).
- **DOI Normalization:** Crossref and OpenAlex DOIs are normalized to lowercase without URL prefixes (`10.48550/arxiv.1706.03762`) to prevent duplicate paper nodes across sources.
- **Evidence Provenance:** Every relationship stores `confidence` (`EXACT`, `HIGH`, `SUPPORTED`), `evidence_field` (e.g. `authorships.author`, `tags.dataset`, `claims.P108`), and direct `provenance_url`.
- **FalkorDB Isolation:** Public data is stored in `nexusact_public` with indexed lookup on `id` across all node types (`Model`, `Dataset`, `Paper`, `Organization`, `Person`, `Topic`, `SourceRecord`), completely preserving the isolation of software repository graphs (`nexusact_main`, `repo_{slug}`).

### 4.3 Universal Ask GAF Workflow (`backend/app/agent/discovery_planner.py`)
1. User provides natural language inquiry (e.g. *"Which organizations publish models related to transformer research?"*).
2. Discovery planner decomposes question into target entity types, relationship focus, and approved source selection.
3. Connectors execute bounded queries against public APIs, returning typed `SourceRecord`s.
4. `PublicGraphPersister` idempotently upserts nodes, source records, and typed edges into FalkorDB.
5. FalkorDB Cypher traverses multi-hop paths up to depth 4 between discovered entities.
6. Returns synthesized findings with explicit coverage notes and limitation disclosures.

---

## 5. Frontend Navigation & User Experience (React 19)

The React frontend (`frontend/src`) features a coherent 5-mode workspace:
1. **Software Graph:** Repository onboarding, AST dependency graph, reverse impact analysis, reviewer rankings, and counterfactual simulation.
2. **Universal Ask GAF:** Interactive natural-language exploration across all 4 public sources with real-time connector health monitoring and suggested inquiries.
3. **AI Ecosystem:** Dedicated view for models, datasets, creators, and explicit `USES_DATASET` links.
4. **Research & Citations:** Scholarly papers, authors, university affiliations, topic taxonomies, and citation traversal.
5. **Diagnostics:** Real-time database latency, memory stats, graph sizes, and connection status.

---

## 6. Automated Quality Gate & Test Results

All quality suites executed locally and verified:

```powershell
.\scripts\check.ps1
```

| Check | Tool / Suite | Scope | Result | Details |
|---|---|---|---|---|
| **Python Linting** | `ruff check .` | Whole workspace | **PASSED** | 0 errors |
| **Python Formatting** | `ruff format --check .` | 85 files | **PASSED** | 85 files clean |
| **Python Type Check** | `mypy backend mcp_server` | 61 source files | **PASSED** | 0 errors |
| **Automated Tests** | `pytest -v` | Unit, Smoke, Integration | **PASSED** | **74/74 passed in 22.4s** |
| **Frontend Linting** | `oxlint` | 23 files | **PASSED** | 0 errors, 0 warnings |
| **Frontend Tests** | `vitest run` | 2 test suites | **PASSED** | **8/8 passed in 1.8s** |
| **Production Build** | `tsc -b && vite build` | Client bundle | **PASSED** | Dist built in 499ms |

### Test Count Growth
- Phase 6 Baseline: 65 Pytest tests
- Phase 7 Final: **74 Pytest tests** (+9 new comprehensive integration tests covering all 4 source connectors, graph persistence, planner heuristics, and discovery API endpoints).

---

## 7. Security Hardening & Safe Public Ingestion

1. **Strict URL Rejection:** Outbound source connectors use hardcoded `API_BASE` constants. User-provided queries cannot alter the target destination host or scheme.
2. **Untrusted Data Boundaries:** Remote descriptions, tags, and model cards are parsed strictly as data strings and never evaluated as instructions or shell commands.
3. **Resource Caps:** Hard limits enforced across all queries (max 20 records, 10s timeout, 512 KB response buffer cap).
4. **Graph Query Parameterization:** All Cypher statements utilize `$param` bindings to prevent injection.
5. **No Blind GitHub Writes:** External GitHub write actions remain strictly protected behind canonical SHA-256 payload approval and duplicate reconciliation markers.

---

## 8. Git Release Verification

- **Current Working Tree:** Clean, fully verified.
- **Remote Branch:** `master`
- **Verification Command:** `.\scripts\check.ps1` -> `ALL QUALITY CHECKS PASSED SUCCESSFULLY!`
