# NexusAct — Live Demonstration Script (Phase 6 Release)

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Target:** Live Hackathon / Production Demo  
**Audience:** Technical evaluators, architects, and engineering leaders  

---

## 1. Prerequisites & Environment Setup

Verify local services are online before starting the presentation:

```powershell
# 1. Start services locally or via Docker Compose
.\scripts\start.ps1

# 2. Confirm readiness and database connectivity
curl http://localhost:8000/api/v1/health/readiness
# Expected: {"status":"READY","database_connected":true,"primary_graph_available":true}

# 3. Open browser to the interactive workspace
# Frontend URL: http://localhost:5173  (or http://localhost:3000 in production Docker)
```

---

## 2. Step-by-Step Live Demonstration Flow

### Scene 1: Repository Onboarding & Graph Ingestion

1. In the header bar, click **"+ Onboard Repo"**.
2. **Local Repository Demo:**
   - Enter Local Path: `.` (or choose a test repository).
   - Display Name: `NexusAct (Self-Analysis)`
   - Click **"Register & Ingest"**.
3. **What to highlight to the audience:**
   - Real AST parsing extracts internal module namespaces (`backend.app.graph.tools.impact`).
   - Resolves relative imports (`from .impact import resolve_module_id`).
   - Extracts genuine Git commit history and author metadata without executing build scripts.
   - Idempotent: repeated ingestions update revision metadata without duplicate nodes.

---

### Scene 2: Natural-Language Investigation & Dynamic Entity Resolution

1. In the investigation prompt bar, type a conversational engineering question:
   > *"What happens if we refactor or remove the simulation tool?"*
2. Leave the module identifier field empty (testing dynamic entity resolution).
3. Click **"Run Investigation"** (or press Enter).
4. **What to highlight to the audience:**
   - **Entity Resolver:** Automatically extracts `"simulation"` from free-form text, matches `backend.app.graph.tools.simulation` with `EXACT` or `HIGH` confidence.
   - **Ambiguity Detection:** Demonstrate typing a vague query like *"What breaks if I change tools?"*; observe candidate chips prompting for clarification rather than hallucinating an arbitrary target.

---

### Scene 3: Bounded Reverse Impact Traversal (`trace_impact`)

1. Observe the **Dependency Impact** section in the investigation report.
2. **What to highlight to the audience:**
   - **Correct Edge Direction:** In static analysis, `A imports B` means `A -[:DEPENDS_ON]-> B`. Therefore, changing `B` impacts `A` (upstream reverse traversal).
   - Upstream dependents: `backend.app.api.endpoints.investigation`, `mcp_server.server`, `backend.app.agent.planner`.
   - Bounded path depth (1 to 4 hops) prevents unbounded query blowup.

---

### Scene 4: Evidence-Backed Contributor Discovery (`who_knows`)

1. Scroll to the **Reviewer Recommendations** section.
2. **What to highlight to the audience:**
   - Transparent 4-part scoring formula:
     $$\text{Score} = 0.40 \times \text{FilesTouched} + 0.30 \times \text{Recency} + 0.20 \times \text{Ownership} + 0.10 \times \text{Reviews}$$
   - Direct commit authors are credited.
   - **Honest Evidence Gaps:** If peer reviews or PR metadata are not available locally or on GitHub, NexusAct honestly flags `NO_REVIEW_DATA` or `UNAVAILABLE` rather than fabricating synthetic reviews.

---

### Scene 5: Counterfactual Simulation (`simulate_remove_module`)

1. Scroll to the **Counterfactual Simulation** section.
2. Click on the **"Simulated Scenario"** tab.
3. **What to highlight to the audience:**
   - **Zero Corruption Guarantee:** NexusAct executes `GRAPH.COPY` to create an ephemeral isolated clone (`scen:<uuid>`).
   - The target module is excised from the clone graph.
   - **Blast Radius & Path Analysis:**
     - Computes true *Disappeared Paths* (callers that lost all routes to downstream dependencies).
     - Computes true *Surviving Paths* (callers that retained alternate surviving routes).
   - In the temporary copy's `finally` block, the ephemeral graph is deleted. The source graph remains 100% intact and unchanged.

---

### Scene 6: Path Verification & Cryptographic Action Proposal

1. Navigate to the **"Action & Issue Proposal"** tab.
2. **What to highlight to the audience:**
   - **Path Verifier:** Audits all traversed paths against FalkorDB, confirming every node, edge, and source file exists. Status: `VERIFIED`.
   - **Action Proposal:** Generates an actionable issue markdown summary with blast radius and suggested reviewers.
   - **Cryptographic Binding:** The proposal computes a canonical SHA-256 payload hash.
   - **Safety First:** If `GITHUB_TOKEN` is not configured, NexusAct provides a safe, non-destructive markdown preview. If configured, external issue submission requires the exact approved hash and embeds a duplicate reconciliation marker (`<!-- GAF-ACTION-MARKER:<hash> -->`).

---

## 3. Demonstration Failure & Recovery Scenarios

| Scenario | System Reaction | Demonstration Point |
|---|---|---|
| **Invalid GitHub URL** (e.g. `http://...` or embedded credentials) | Rejected at validation boundary with clear error | SSRF protection and security boundary |
| **Missing Model Credentials** | Switches transparently to deterministic heuristic planner | Resilience: local intelligence never breaks |
| **FalkorDB Unavailable** | Health API reports `UNHEALTHY` / `NOT_READY` with diagnostics | Honest monitoring; no false green states |
| **Ambiguous Target** | Returns `AMBIGUOUS` with candidate selection chips | AI safety: never acts on ambiguous intent |
