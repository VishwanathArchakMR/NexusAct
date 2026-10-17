# NexusAct — Live Demonstration Script (Phase 20 Judge-Ready Edition)

**Product:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Hackathon Track:** *Agents That Act on Connected Data*  
**Primary Database:** FalkorDB v4.4.1 (Redis Protocol / Cypher)  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  

---

## 1. Prerequisites & Startup

Start services using the established scripts:

```powershell
# 1. Start all services (FalkorDB + FastAPI + Vite Frontend)
.\scripts\start.ps1

# 2. Check system status
.\scripts\status.ps1
# Expected Output:
#   FalkorDB        READY        127.0.0.1:6379 (Live Cypher engine operational)
#   FastAPI         READY        http://127.0.0.1:8000
#   Vite Frontend   READY        http://localhost:5173

# 3. Direct API readiness probe
Invoke-RestMethod http://127.0.0.1:8000/ready
# Expected: {"status":"READY","database":{"connected":true,"host":"127.0.0.1","port":6379,"graph":"nexusact_main"}}
```

Open your browser to: **`http://localhost:5173`**.

---

## 2. Demonstration Walkthrough (Click-by-Click)

### Scene 1: Canonical Source Freshness & Multi-Tenant Graph Isolation
1. **Top Context Bar**: Notice the active repository: `NexusAct (Local Workspace)`, pinned Git commit SHA, and `FRESH` badge.
2. Click the repository dropdown:
   - `NexusAct (Local Workspace)` (`nexusact_main` — ~1,400 nodes, ~1,830 edges)
   - `semantica-agi/semantica` (`repo_semantica_agi_semantica` — ~1,067 modules, ~7,387 edges)
   - `LifeAssist AI (TypeScript)` (`repo_test_p12_ts` — multi-language TypeScript dependency graph)
3. **Key Points for Evaluators:**
   - Every repository is strictly isolated into its own physical FalkorDB graph (`nexusact_main`, `repo_<slug>`).
   - System and demo graphs (`nexusact_main`, `nexusact_fraud_demo`) are protected from arbitrary deletion or cross-contamination.

---

### Scene 2: Genuine Multi-Hop Investigation & Directed Path Visualization
1. Select `NexusAct (Local Workspace)`.
2. In the investigation prompt bar, enter:
   > *"Trace the path from the API router to graph storage client"*
3. Click **"Run Investigation"**.
4. **Key Points for Evaluators:**
   - **Autonomous Tool Execution**: The agent selects `nexusact_shortest_path` over MCP with source `backend.app.api.router` and target `backend.app.graph.client`.
   - **Genuine 2-Hop / 3-Node Traversal**: FalkorDB executes shortest path traversal over AST-derived import relationships:
     $$\text{mod:backend.app.api.router} \xrightarrow{\text{DEPENDS\_ON}} \text{mod:backend.app.api.endpoints.investigation} \xrightarrow{\text{DEPENDS\_ON}} \text{mod:backend.app.graph.client}$$
   - **Investigation Path Mode**: Notice the canvas switches to **Investigation Path** view, laying out the nodes in a horizontal sequence with glowing animated directional arrows and path chip breadcrumbs.
   - **Network Overview Toggle**: Click **Network Overview** to see the full hierarchical neighborhood lanes (callers on the left, focus node in center, downstream libraries on the right).
   - **Interactive Canvas**: Test zoom (+/-), pan, node dragging, search filtering, and node selection to view metadata in the right-side inspector.

---

### Scene 3: Evidence-Grounded Panel Explanations & Caching
1. Notice the **Panel Explanation card** at the top of the Graph Explorer:
   - **Takeaway**: Plain-English 1-2 sentence executive summary.
   - **What you are looking at**: Clear description of the graph view.
   - **What NexusAct found**: Concrete facts directly extracted from FalkorDB.
   - **Why it matters**: Practical architectural impact for software engineers.
   - **Evidence & Relationships**: Exact node IDs and graph relationships backing the conclusion.
   - **Confidence & Limitations**: Distinguishes static AST imports from dynamic reflection.
   - **Provider Status**: Labeled honestly as `GEMINI_ACTIVE`, `CACHED`, or `FALLBACK_ACTIVE`.
2. Click between panels in the left sidebar (e.g. *Code Inspector*, *Reviewers & Authors*, *Agent MCP Trace*).
3. Notice:
   - Each panel provides a **panel-specific, grounded explanation**.
   - Subsequent tab visits return instantaneous `CACHED` responses via SHA-256 evidence hashing.
   - Active investigation ID and graph state remain fully preserved across tab changes.

---

### Scene 4: Code Inspector with Line Spans & AST Symbols
1. Click **Code Inspector** in the left sidebar under *Explore*.
2. Browse the repository tree to `backend/app/graph/client.py`.
3. Notice:
   - Exact syntax-highlighted source code with line numbers.
   - AST symbol outline listing `FalkorDBClient`, methods (`execute_cypher`, `select_graph`, `ping`), and docstrings.
   - Direct bidirectional linkage: Click on a graph module to navigate to its source file; click "Trace Dependencies" to explore connected graph callers.

---

### Scene 5: Isolated Counterfactual Scenario Simulation
1. Click **Scenario Simulation** under *Analyze*.
2. Click **"Run Simulation on backend.app.graph.client"**:
   - NexusAct executes `GRAPH.COPY` to an isolated scenario graph in FalkorDB (`scen:<uuid>`).
   - Excises the target module and re-computes path reachability.
   - Deletes the temporary scenario graph, leaving the master graph 100% untouched.
3. Observe:
   - **Blast Radius Score**: Calculated based on disrupted vs surviving dependency routes.
   - **Visual Diff**: Disrupted dependency paths highlighted in dashed red, surviving alternate routes in green.

---

### Scene 6: Public Vulnerability Security Triage (`nexusact_security_triage`)
1. In the left navigation, click **Security Triage** under *Specialized Workflows*.
2. Run security triage against the repository:
   - Inspects `package.json` and `requirements.txt`.
   - Queries Google OSV.dev in real time (`https://api.osv.dev/v1/query`).
   - Discloses honest audit results: 0 known public advisories found in pinned production dependencies.
   - Shows full manifest coverage, ecosystem, and reachability trace.

---

### Scene 7: Real-Data Financial Fraud Investigation Engine (Phase 21)
1. In the left navigation, click **Fraud Investigation** under *Specialized Workflows*.
2. Observe the dedicated, isolated financial workspace:
   - **Context Isolation**: Notice that codebase Git commit SHAs and repository overview cards are completely isolated from this tab.
   - **Visual Semantics**: Notice the persistent node legend with dedicated domain colors: Account (`#2563eb`), Transaction (`#7c3aed`), Device (`#0d9488`), IP Address (`#d97706`), Merchant (`#16a34a`).
3. Click **"Load Benchmark"** to instantly ingest the bundled anonymized AML Transaction Benchmark into an isolated FalkorDB graph namespace (`fin_<dataset_id>`):
   - Alternatively, click **"Import Dataset"** to upload your own transaction CSV/TSV/JSON file with automatic delimiter sniffing, column profiling, and interactive schema mapping.
4. Click **"Investigate Graph"**:
   - Executes genuine multi-hop OpenCypher graph traversals across the isolated FalkorDB namespace.
   - **Multi-Hop Circular Transfer Ring**: Detects 3-hop money-laundering cycle:
     $$\text{ACC\_ALPHA} \xrightarrow{\$10,000} \text{ACC\_BETA} \xrightarrow{\$9,500} \text{ACC\_GAMMA} \xrightarrow{\$9,000} \text{ACC\_ALPHA}$$
     with 90.0% capital retention and rapid velocity.
   - **Shared Infrastructure**: Identifies hardware device `DEV_IPHONE_99` and client IP `198.51.100.12` shared between `ACC_ALPHA` and `ACC_BETA`.
   - **Interactive Path Tracing**: Click on any finding to highlight the multi-hop route directly on the graph canvas.
   - **Benign Control Baselines**: Audits linear consumer retail accounts (`ACC_SAFE_1`, `ACC_SAFE_2`), confirming they are classified as normal benign spending.
   - **Transparent Risk Scoring**: Shows mathematical risk factor decomposition (Circular Routing 0.45, Shared Devices 0.25, Velocity Bursts 0.15).
   - **Read-Only Compliance Guarantees**: Discloses strict read-only guarantees (no funds transfers or account freezes) and recommends qualified human compliance review.

---

### Scene 8: Cryptographically Bound Action Proposal
1. Click **Verified Action** under *Evidence & Action*.
2. Observe the generated GitHub issue proposal:
   - Title, affected modules, blast radius, and recommended reviewers.
   - Bound to a deterministic **SHA-256 payload hash**.
   - State machine: `PROPOSED` $\rightarrow$ `APPROVED` $\rightarrow$ `VERIFIED`.
   - Strict human-in-the-loop approval requirement before any external mutation can occur.

---

## 3. Truthful AI Disclosure

| Function | When Gemini API Key Configured | When Key Absent (Fallback) |
|---|---|---|
| **Adaptive Tool Planning** | Gemini selects next MCP tool from schema | Deterministic architectural rule engine |
| **Panel Explanations** | Gemini synthesizes plain-English narrative from structured facts | Deterministic evidence template grounded in FalkorDB |
| **Status Labeling** | `GEMINI_ACTIVE` (`gemini-2.5-flash`) | `FALLBACK_ACTIVE` / `NOT_CONFIGURED` |

NexusAct never reports AI generation when running deterministic heuristics.
