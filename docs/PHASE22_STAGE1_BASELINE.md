# Phase 22 Stage 1 Baseline Report: Runtime Recovery & Investigation Data-Flow Repair

**Repository**: `https://github.com/VishwanathArchakMR/NexusAct`  
**Track**: Agents That Act on Connected Data  
**Primary Graph Database**: FalkorDB v4.4.1 (RedisGraph protocol)  
**Starting Baseline Commit**: `f7187b6b1bfd21a385c3dbfb46646b415bd22070` (Phase 21 Complete)  
**Git Working Tree**: Clean, `master` branch  

---

## 1. Executive Summary & Context

NexusAct previously completed Phase 21 with a green test suite (355 passed backend tests, 88 passed frontend unit tests, 0 lint or mypy errors, verified on GitHub Actions run 39064261851). However, runtime inspection with a running FalkorDB instance, FastAPI backend (`http://127.0.0.1:8000`), and Vite frontend (`http://127.0.0.1:5173`) revealed 5 critical runtime regressions and data-flow discrepancies:

1. **Investigation Workflow Failure on Selected Repositories (Priority 1)**:
   - When a repository other than `repo:local_nexusact` (such as `repo:vishwanatharchakmr_aletheiaos`) is selected in the workspace, clicking **Investigate** with common architecture/API questions results in a `CONTRADICTED` verification status and empty graph explorer.
   - Root cause: `AdaptiveInvestigationAgent.plan_investigation` in `backend/app/agent/planner.py` (lines 350-354 and 885-896) had hardcoded fallback target resolution to NexusAct's internal modules (`backend.app.api.router` and `backend.app.graph.client`). Because these modules do not exist in foreign graphs (`repo_vishwanatharchakmr_alethe`), the shortest path MCP tool (`nexusact_shortest_path`) executed an impossible traversal and returned `found: false`, marking the investigation contradicted and yielding 0 visual nodes/edges.

2. **Diagnostics SHA & Metadata Mismatch (Priority 4)**:
   - In the Diagnostics view (`/diagnostics`), the Repository & Graph Freshness card displayed commit SHA `f7187b6` even when a remote repository such as AletheiaOS (`83d1ae15`) was selected.
   - Root cause: `backend/app/api/endpoints/health.py` (`get_system_status`, line 139) ignored the client's currently active repository and unconditionally fetched `repos[0]` (`repo:local_nexusact`).

3. **Recent Graph Investigations Misclassification & Hardcoded Fallback (Priority 5)**:
   - The Recent Graph Investigations panel in `InvestigationCenter.tsx` displayed previous investigations as "Codebase Walkthrough" targeting `nexusact_main` regardless of the actual workflow mode or target graph.
   - Root cause: `AdaptiveInvestigationAgent` recorded `(:Investigation)` nodes in FalkorDB without indexing the investigation mode, repository ID, or commit SHA. The frontend `InvestigationCenter.tsx` was querying `/api/v1/discover/investigations` (an endpoint designed solely for public data discovery in `nexusact_public`) and hardcoding `modeLabel = "Codebase Walkthrough"` and `targetGraph = "nexusact_main"`.

4. **Workspace Tabs Dependent on Investigation (Priority 3)**:
   - Upon selecting a repository, tabs such as Code Inspector, Reviewers & Authors, Neighborhood & Paths, and Provenance showed blank or uninformative states until the user manually entered a question and pressed Investigate.
   - Root cause: Tab components strictly gated rendering on `report !== null` instead of initializing repository-level metadata, module lists, file trees, and graph overviews immediately upon repository selection.

5. **LLM Provider Configuration & Bounded Connectivity (Priority 2)**:
   - Diagnostics correctly identified `NOT_CONFIGURED: No server-side GEMINI_API_KEY detected. Rule-based heuristic fallback is active and healthy.`
   - Need to ensure robust `.env` resolution independent of invocation directory, support both `GEMINI_API_KEY` and `GOOGLE_API_KEY`, preserve truthful fallback disclosures without faking connectivity, and separate planner from explanation generation in status checks.

---

## 2. Detailed Reproduction Traces

### Issue 1: Investigation Target Hardcoding & Failure on AletheiaOS
- **API Call**: `POST /api/v1/investigate`
  ```json
  {
    "question": "How does the API route requests to the graph storage engine?",
    "target_repo_id": "repo:vishwanatharchakmr_aletheiaos",
    "workflow": "codebase_investigation"
  }
  ```
- **Observed Behavior**:
  - Request succeeded with HTTP 200, but returned:
    - `verification_status`: `"CONTRADICTED"`
    - `target_name`: `"backend.app.api.router -> backend.app.graph.client"` (NexusAct modules, not AletheiaOS modules!)
    - `tool_executions[1].output`: `{"found": false, "source": "mod:backend.app.api.router", "target": "mod:backend.app.graph.client", "graph": "repo_vishwanatharchakmr_alethe"}`
    - Graph Explorer on frontend showed empty subgraph.
- **Expected Behavior**:
  - For non-nexusact repositories, target resolution must query the selected graph's actual modules (`repo_vishwanatharchakmr_alethe`), finding candidates like `mod:aletheia.core` or `mod:aletheia.api`. If no path exists, report an honest `UNRESOLVED` or informative finding rather than asserting contradicted based on nonexistent foreign modules.

### Issue 2: Diagnostics Displaying Wrong Repository Revision
- **API Call**: `GET /api/v1/system/status`
- **Observed Behavior**:
  - Returned: `{"repository_freshness": {"repository_id": "repo:local_nexusact", "commit_sha": "f7187b6b1bfd21a385c3dbfb46646b415bd22070"}}`
  - When frontend had selected `repo:vishwanatharchakmr_aletheiaos` (`83d1ae15`), the diagnostics panel showed `f7187b6`, leading the user to believe the freshness check was broken or cross-polluted.
- **Expected Behavior**:
  - `GET /api/v1/system/status?repo_id=repo:vishwanatharchakmr_aletheiaos` must return the freshness, revision, and graph state of the requested repository.

### Issue 3: Recent Graph Investigations Querying Wrong Store
- **Observed Behavior**:
  - `InvestigationCenter.tsx` calls `fetchSavedInvestigations()`, which hits `/api/v1/discover/investigations`.
  - It returned public discovery nodes (`uinv_...`) from `nexusact_public` and rendered them with hardcoded badge "Codebase Walkthrough" and graph "nexusact_main".
  - Real codebase investigations, security investigations, and financial investigations conducted in the workspace were not reflected in the recent investigations list.
- **Expected Behavior**:
  - Real investigations recorded across workspace graphs must be stored and queried via a unified recent investigations endpoint with their actual `workflow`, `repo_id`, `graph_name`, and timestamp.

---

## 3. Plan of Record for Stage 1 Repairs

1. **Priority 1**: Dynamic module resolution in `planner.py` based on `target_graph`.
2. **Priority 2**: Server-side config & `.env` resolution, provider alias support (`GEMINI_API_KEY` / `GOOGLE_API_KEY`), and bounded LLM connectivity diagnostic endpoint.
3. **Priority 3**: Independent tab initialization upon repository selection in `InvestigationWorkspace.tsx`.
4. **Priority 4**: Source-specific `repo_id` parameter in `system/status` and repository freshness check.
5. **Priority 5**: Unified recent investigations persistence and endpoint (`/api/v1/investigation/recent`) with updated frontend consumption.
