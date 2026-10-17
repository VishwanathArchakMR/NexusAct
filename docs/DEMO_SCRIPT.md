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

### Scene 7: Isolated Synthetic Fraud Investigation (`nexusact_investigate_fraud`)
1. In the left navigation, click **Fraud Topology** under *Specialized Workflows*.
2. Click **"Run Fraud Investigation"**:
   - Operates strictly in the isolated `nexusact_fraud_demo` graph.
   - **Prominent Synthetic Disclaimer**: Clearly declares all records and individuals are synthetic.
   - **Multi-Hop Circular Transfer Ring**: Detects 3-hop money-laundering cycle:
     $$\text{acc:101} \xrightarrow{\$10,000} \text{acc:102} \xrightarrow{\$9,500} \text{acc:103} \xrightarrow{\$8,200} \text{acc:101}$$
   - **Shared Infrastructure**: Identifies `dev:iphone_xyz` shared between `acc:101` and `acc:103`.
   - **Benign Control Baselines**: Audits linear consumer retail accounts (`acc:201`, `acc:202`), confirming they are classified as normal benign spending.

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
