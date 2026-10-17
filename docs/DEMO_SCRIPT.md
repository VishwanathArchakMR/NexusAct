# NexusAct — Live Demonstration Script (Phase 14 Hackathon Edition)

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Hackathon Track:** *Agents That Act on Connected Data*  
**Primary Database:** FalkorDB v4.4.1 (Redis Protocol / Cypher)  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  

---

## 1. Prerequisites & Clean Runtime Verification

Before beginning the demo, verify that all local services are healthy and ready:

```powershell
# 1. Start all services reliably (handles Docker / WSL2 and transient AOF loading)
.\scripts\start.ps1

# 2. Inspect authoritative system status
.\scripts\status.ps1
# Expected Output:
#   FalkorDB        READY        127.0.0.1:6379 (Live Cypher engine operational)
#   FastAPI         READY        http://127.0.0.1:8000
#   Vite Frontend   READY        http://localhost:5173

# 3. Direct API readiness probe
Invoke-RestMethod http://127.0.0.1:8000/ready
# Expected: {"status":"READY","database":{"connected":true,"host":"127.0.0.1","port":6379,"graph":"nexusact_main"}}
```

Open the web interface in your browser: **`http://localhost:5173`**.

---

## 2. Step-by-Step Live Demonstration Flow

### Scene 1: Multi-Repository Selection & Physical Graph Separation
1. In the header bar, observe the **Repository Selector**.
2. Notice the pre-ingested repositories:
   - `NexusAct (Local Workspace)` (`nexusact_main` — 786 modules, 738 edges)
   - `semantica-agi/semantica` (`repo_semantica_agi_semantica` — 1,067 modules, 7,387 edges)
   - `LifeAssist AI (TypeScript)` (`repo_test_p12_ts` — multi-language TypeScript dependency graph)
3. **What to highlight to judges:**
   - NexusAct operates on **distinct physical graphs** in FalkorDB.
   - Selecting a repository locks all queries, MCP tools, and action proposals strictly to that graph. No cross-graph leakage or silent fallback.

---

### Scene 2: Codebase Investigation & Real Multi-Hop Reasoning
1. Select `NexusAct (Local Workspace)`.
2. In the investigation prompt bar, enter:
   > *"What could break if I change backend.app.graph.client?"*
3. Click **"Run Investigation"**.
4. **What to highlight to judges:**
   - **MCP Tool Execution Trace:** Observe the sequential execution of tools registered over the Model Context Protocol:
     1. `nexusact_trace_impact`: Traverses reverse dependency paths up to 4 hops in FalkorDB, discovering 27 dependent modules (e.g. `backend.app.agent.planner`, `backend.app.api.endpoints.investigation`).
     2. `nexusact_who_knows`: Evaluates contributor ownership evidence from Git commit history.
     3. `nexusact_simulate_remove_module`: Runs isolated counterfactual simulation.
   - **Multi-Hop Path Verification:** The PathVerifier audits traversed paths against FalkorDB, confirming every node, edge, and file path exists (`VERIFIED`).
   - **Deterministic Fallback:** Show that the multi-hop reasoning operates completely deterministically even without an external LLM key, or via Google Gemini when configured.

---

### Scene 3: Interactive Graph Canvas & Visual Counterfactual Simulation
1. Switch to the **Graph Canvas** view.
2. Toggle between **Light Theme** and **Dark Theme** using the theme switch.
3. Observe the high-contrast visualization:
   - Central focus on `backend.app.graph.client`.
   - Directed edges pointing in canonical `DEPENDS_ON` direction.
   - Distinct node types (Modules, Files, Commits, Contributors).
   - Smooth zoom and pan controls with passive-wheel safety.
4. Click on the **"Simulated Scenario"** tab:
   - **Zero-Corruption Guarantee:** NexusAct cloned the graph via FalkorDB `GRAPH.COPY` to an ephemeral clone (`scen:<uuid>`), excised the module, evaluated path reachability, and deleted the clone. The master graph remained 100% unchanged.
   - **Blast Radius & Disrupted Paths:** Disrupted dependency routes are highlighted with dashed red edges, while surviving alternate paths glow in green.

---

### Scene 4: Public Vulnerability Security Triage (`nexusact_security_triage`)
1. In the investigation prompt bar, enter:
   > *"Triage vulnerabilities affecting repository dependencies"*
2. Click **"Run Investigation"**.
3. **What to highlight to judges:**
   - NexusAct inspects declared manifests (`package-lock.json`, `package.json`, `requirements.txt`) in the active repository.
   - Queries the public **Google OSV database** (`https://api.osv.dev/v1/query`) in real time.
   - Persists `PackageDependency` and `Vulnerability` nodes in FalkorDB with `[:HAS_VULNERABILITY]` and `[:USES_PACKAGE]` relationships.
   - Honest uncertainty disclosure: If a package version is ambiguous, or manifests are absent, NexusAct flags `MANIFESTS_UNAVAILABLE` or `NO_MANIFESTS_FOUND` rather than falsely claiming safety.

---

### Scene 5: Isolated Synthetic Fraud Investigation (`nexusact_investigate_fraud`)
1. In the prompt bar, enter:
   > *"Investigate suspicious synthetic transfers and explain how accounts are connected"*
2. Click **"Run Investigation"**.
3. **What to highlight to judges:**
   - **Synthetic Graph Isolation:** Operates strictly on `nexusact_fraud_demo`.
   - **Prominent Disclaimer:** Clearly labeled: *"This investigation operates strictly on synthetic, deterministic demonstration records... No real-world individuals or accounts are represented."*
   - **Multi-Hop Circular Cycle Detection:** Traverses `(a1)-[:SENDS_TO]->(a2)-[:SENDS_TO]->(a3)-[:SENDS_TO]->(a1)` (hop depth = 3) detecting rapid fund redirection totaling $27,700 within 3 hours.
   - **Shared Infrastructure Indicator:** Detects `dev:iphone_xyz` shared between `acc:101` and `acc:103`. Honestly classifies shared infrastructure as `MEDIUM` severity risk indicator requiring corroborating transaction proof, not standalone proof of fraud.
   - **Benign Control Audit:** Audits control accounts `acc:201` and `acc:202`, proving linear retail merchant spending is recognized as `BENIGN_NORMAL` and never misclassified.

---

### Scene 6: Cryptographic Action Proposal & Safe Internal FalkorDB Persistence
1. Scroll down to the **Action & Issue Proposal** card.
2. Observe the proposal generated specifically from the active investigation:
   - Distinct tailored proposals for Codebase Impact, Security Triage, and Fraud Review.
   - Includes canonical SHA-256 payload hash and reconciliation markers.
3. Click **"Save Internal Task"**:
   - Persists the action in FalkorDB as a structured follow-up item with state `SAVED`.
   - When `GITHUB_TOKEN` is unset, remote writes remain strictly locked. No accidental or unauthenticated network dispatches occur.

---

## 3. Demo Closing & Judge Takeaways

1. **Graph-Native Core:** NexusAct does not merely use FalkorDB as a database; it uses FalkorDB's Cypher traversals, multi-hop pathfinding, PageRank centrality, and `GRAPH.COPY` simulation to drive every agent decision.
2. **Honest AI:** Discloses uncertainties, evidence gaps, and synthetic data disclaimers. Never invents nonexistent edges or owners.
3. **Safe Action Guardrails:** Every external action proposal is grounded in verified graph evidence, bound by cryptographic hash, and protected by authentication gates.
