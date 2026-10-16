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

### Scene 7: Universal Ask GAF — Multi-Domain Knowledge Discovery

1. In the top navigation bar, click on **"Universal Ask GAF"**.
2. **What to highlight to the audience:**
   - **4 Live Approved Connectors:** Hugging Face Hub, OpenAlex Scholarly Graph, Crossref Metadata, and Wikidata. All show real-time health checks.
   - **Fixed API Base Security:** Connectors use immutable class constants; arbitrary user URLs cannot be fetched.
3. In the inquiry bar, type:
   > *"Which organizations publish models related to transformer research?"*
4. Click **"Investigate"**.
5. **Observe the Results:**
   - Universal Discovery Planner selects Hugging Face, OpenAlex, and Wikidata.
   - Discovers models, creators, papers, and topics with bounded API queries.
   - Persists all entities idempotently into FalkorDB `nexusact_public`.
   - Results show exact evidence tags (e.g. `authorships.author`, `tags.dataset`, `claims.P108`).
   - Every claim features a clickable **Source Record** provenance URL.
   - Any missing coverage or partial failure is honestly disclosed in the Coverage Limitations box.

---

### Scene 8: AI Ecosystem & Citation Graph Exploration

1. Click on the **"AI Ecosystem"** tab.
   - Focuses search on models and datasets.
   - Query: *"Which datasets are documented as used to train open models?"*
   - Highlights explicit `USES_DATASET` links grounded in metadata tags, strictly avoiding false inferences.
2. Click on the **"Research & Citations"** tab.
   - Focuses search on scholarly papers and citation graphs.
   - Resolves lowercase DOIs across OpenAlex and Crossref to avoid duplicate nodes.
   - Traverses `CITES` and `AFFILIATED_WITH` relationships to identify academic research clusters.

---

---

### Scene 9: Interactive Graph Explorer & Multi-Hop Path Highlight

1. Click on the **"Dependency Graph"** tab in the Software Graph workspace.
2. **What to highlight to the audience:**
   - **Visualized Graph (No Blank Canvas):** Real nodes (rectangles with names) and directed dependency edges (arrows in `DEPENDS_ON` direction).
   - **Three-Region Layout:**
     - Left: Upstream callers (dependents).
     - Center: Target focus module.
     - Right: Downstream dependencies.
   - **Interactive Pan & Zoom:** Drag the canvas to pan; use wheel or `+`/`-`/`fit-to-view` buttons.
   - **Contextual Inspector:** Click on any node to slide open the inspector panel displaying ID, in/out degrees, caller lists, and a "Focus Target" button. Click an edge to inspect its source file and evidence type.
   - **Multi-Hop Path Glow:** The verified multi-hop relationship path (`A -> B -> C -> D`) is illuminated with a glowing stroke and breadcrumb sequence.
   - **Theme Switcher:** Click the Sun/Moon toggle in the header. Show seamless contrast transition between clean Light mode (default) and dark mode with high contrast SVG labels and panels.

---

### Scene 10: Security Triage Workflow

1. Submit a security-focused prompt:
   > *"Security triage: what is the blast radius and remediation owners if backend.app.core.config is compromised?"*
2. **What to highlight to the audience:**
   - Agent dynamically selects security triage tools: `nexusact_simulate_remove_module` &rarr; `nexusact_trace_impact` &rarr; `nexusact_who_knows`.
   - Action Proposal automatically generates: `[NexusAct Security Triage] Remediation & blast radius for backend.app.core.config`.
   - Distinguishes structural blast radius from runtime crash assumptions.

---

## 3. Video Recording Checklist for Submission

Before recording the 3–5 minute hackathon demo video, verify each item:

- [ ] **Resolution & Audio:** 1080p minimum, clear microphone audio, no background noise.
- [ ] **Track Mention:** Clearly state the hackathon track: **"Agents That Act on Connected Data"** using **FalkorDB v4.4.1**.
- [ ] **Connected Data First:** Show that the graph data lives in FalkorDB (e.g. mention Cypher queries and persistent storage).
- [ ] **Flow Order:**
  1. Quick introduction of NexusAct and the GraphAction Fabric (GAF) architecture (30s).
  2. Software Graph: Ingest or select repository, ask natural-language question, show First-Class Investigation Summary (45s).
  3. Interactive Graph Explorer: Pan/zoom canvas, click node to open slide-over inspector, show multi-hop path glow, toggle Light/Dark theme (60s).
  4. Tool Trace & MCP: Show Agent MCP Trace with dynamic tool selection (30s).
  5. Counterfactual Simulation: Show baseline vs. removed module blast radius (30s).
  6. Verified Action: Show evidence-grounded issue proposal with SHA-256 hash and safe approval gate (30s).
  7. Universal GAF (Brief): Show public data search connecting papers and models with source URLs (30s).
  8. Conclusion: Reiterate hackathon track and graph-native intelligence (15s).
- [ ] **No False Claims:** Explicitly note that external GitHub actions require an approved token and are safeguarded by human approval.

---

## 4. Demonstration Failure & Recovery Scenarios

| Scenario | System Reaction | Demonstration Point |
|---|---|---|
| **Invalid GitHub URL** (e.g. `http://...` or embedded credentials) | Rejected at validation boundary with clear error | SSRF protection and security boundary |
| **Missing Model Credentials** | Switches transparently to deterministic heuristic planner | Resilience: local intelligence never breaks |
| **FalkorDB Unavailable** | Health API reports `UNHEALTHY` / `NOT_READY` with diagnostics | Honest monitoring; no false green states |
| **Ambiguous Target** | Returns `AMBIGUOUS` with candidate selection chips | AI safety: never acts on ambiguous intent |
| **Public Source Partial Outage** | Records other sources, isolates failure in `coverage_limitations` | Partial failure tolerance; no cascading crashes |
| **Restart Recovery** | Graph data in FalkorDB persists across restarts | Persistent relationship engine verification |
| **Unresolved Target Module** | Returns `UNRESOLVED` with candidate suggestions | Honest truthfulness; no hallucinated graphs |

