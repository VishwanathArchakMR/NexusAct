# Phase 23 Baseline & Defect Analysis

**Repository**: `https://github.com/VishwanathArchakMR/NexusAct`  
**Track**: Agents That Act on Connected Data  
**Primary Graph Database**: FalkorDB v4.4.1 (RedisGraph protocol)  
**Baseline Commit**: `baad8186ebd8a84939667c79307f94c64791f196`  

---

## 1. Actual Local Baseline & System Boundaries

- **Git HEAD**: `baad8186ebd8a84939667c79307f94c64791f196` on branch `master` (Clean working tree).
- **Remote Tracking**: `origin/master` up to date; remote GitHub Actions CI run `39071763328` is 100% GREEN.
- **FalkorDB Runtime**: Verified active on `127.0.0.1:6379`.
- **FastAPI Backend**: Running on port `8000`.
- **Vite Frontend**: Running on port `5173`.
- **MCP Server**: Defined in `mcp_server/server.py` exposing 9 domain tools over stdio JSON-RPC.

---

## 2. Reproduced Defects & Verified Root Causes

### Defect 1: Scenario Simulation Contradiction & Missing Interactive Flow
- **Observed Symptoms (from User Screenshot)**:
  - Header insight claims: *"Counterfactual removal of 'repository root' disrupted 0 of 0 dependency paths (0% blast radius)."*
  - Immediately below, `CounterfactualDiff` displays: *"No counterfactual simulation executed yet. Run simulate_remove_module to clone the graph and compare before/after paths."*
  - These two panels directly contradict each other. The insight targets a nonexistent module (`repository root`), and the blast radius is misleadingly presented as 0%.
- **Root Cause Analysis in Source Code**:
  1. In `InvestigationWorkspace.tsx` (lines 2021-2043), the Scenario Simulation panel is purely reactive to `report?.simulation_result`. It provides no interactive module selection or "Run Simulation" trigger independent of a prior investigation.
  2. When the user switches to the `simulation` tab before running a counterfactual removal investigation, `sim` is `undefined`.
  3. `PanelExplanation` passes `dataSummary={{ target_module_id: sim?.target_module_id, ... }}` to the backend.
  4. In `backend/app/agent/explanation.py` (lines 140-148):
     ```python
     target = data.get("target_module_id") or target_id or "repository root"
     baseline = data.get("baseline_paths", 0)
     disrupted = data.get("disrupted_paths", 0)
     blast_radius = data.get("blast_radius", 0.0)
     blast_pct = int(blast_radius * 100) if isinstance(blast_radius, (int, float)) else 0
     summary = (
         f"Counterfactual removal of '{target}' disrupted {disrupted} of {baseline} dependency paths "
         f"({blast_pct}% blast radius)."
     )
     ```
     Because `target_module_id` is null, it fell back to `"repository root"` and reported `0 of 0` paths disrupted (`0% blast radius`) as if a simulation had successfully executed and completed with zero blast radius.
- **Required Resolution**:
  - Distinguish explicitly between simulation states: `NOT_REQUESTED`, `PREPARING`, `RUNNING`, `COMPLETED`, `COMPLETED_ZERO_IMPACT`, and `FAILED`.
  - Provide an interactive module picker populated from real modules in the active FalkorDB graph (`MATCH (m:Module) ...`).
  - Wire a dedicated counterfactual execution endpoint and trigger button (`POST /api/v1/investigation/simulate`).
  - Do not render contradictory success insights before a simulation is executed.

---

### Defect 2: Reviewers & Authors Empty State Contradiction
- **Observed Symptoms (from User Screenshot)**:
  - Header insight states: *"Identified 0 contributor(s) with historical expertise on '' and its callers; lead author is Unknown (0 commits)."*
  - Recommends: *"Include the top-ranked contributors as required reviewers on any pull request touching this component."*
  - Right below, the panel says: *"No reviewer recommendations available. Run who_knows or an investigation to identify engineers with relevant commit history."*
  - Contradiction: Advising the user to include top-ranked contributors when 0 contributors and "Unknown" lead author were found.
- **Root Cause Analysis in Source Code**:
  1. In `InvestigationWorkspace.tsx` (lines 2045-2062), `ReviewerRankings` only renders `report?.reviewer_result`. On repository selection without an investigation, `report` is `null`.
  2. There is no automatic loading of repository-level contributors or module-level authors when selecting modules or opening the tab.
  3. In `backend/app/agent/explanation.py` (lines 172-200):
     ```python
     top_name = candidates[0].get("name", "N/A") if candidates else "Unknown"
     top_commits = candidates[0].get("commits_count", 0) if candidates else 0
     total_authors = len(candidates)
     ...
     next_step = (
         "Include the top-ranked contributors as required reviewers on any pull request touching this component."
     )
     ```
     It unconditionally advised assigning top-ranked contributors even when `total_authors == 0`.
- **Required Resolution**:
  - Automatically load contributors for the selected repository and target module upon tab activation.
  - Separate repository-level commit authors from explicit module PR reviewers.
  - Provide truthful, distinct UI states for: (a) No Git history ingested, (b) Snapshot has 0 commits, (c) Selected module has no author touch records, (d) Query failure.
  - Eliminate contradictory next-step advice when no authors exist.

---

### Defect 3: Absence of Right-Side Graph-Grounded LLM Chatbot
- **Current Limitation**:
  - The application only had a search input on the top bar that launched full investigations.
  - No interactive conversational assistant bound to the active repository graph context.
  - No real-time conversational Cypher exploration where users can ask ad-hoc questions ("Why is this module critical?", "Who touched this recently?", "Which components depend on client?").
- **Required Resolution**:
  - Implement a dedicated right-side conversational drawer/panel bound to the selected repository/graph context.
  - Build an end-to-end graph-grounded reasoning pipeline: Question -> Intent & Entity Resolution -> Safe Read-Only Cypher Generation/Validation -> FalkorDB Execution -> Evidence Retrieval -> Grounded LLM Response with visible Cypher trace.
