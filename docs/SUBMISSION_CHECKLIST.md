# NexusAct — Hackathon Submission Checklist (Phase 20 Judge-Ready Edition)

**Competition:** Graph Hacks — WeMakeDevs × FalkorDB (October 15–18, 2026)  
**Track:** *Agents That Act on Connected Data*  
**Product:** NexusAct (Architecture: GraphAction Fabric / GAF)  
**Primary Database:** FalkorDB v4.4.1 (Redis Protocol / Cypher)  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct.git](https://github.com/VishwanathArchakMR/NexusAct.git)  

---

## 1. Submission Metadata & Track Alignment

| Requirement | Value / Location | Status |
|---|---|---|
| **Public Repository** | `https://github.com/VishwanathArchakMR/NexusAct.git` | ✅ Public & Accessible |
| **Selected Track** | **Agents That Act on Connected Data** | ✅ Primary Focus |
| **Primary Database** | **FalkorDB v4.4.1** (Standalone Docker / Managed Redis Protocol) | ✅ Verified (127.0.0.1:6379) |
| **Architecture Tagline** | *Graph-Native AI That Investigates, Simulates, and Acts* | ✅ Validated |
| **Event Dates** | October 15, 2026, 12:01 AM IST – October 18, 2026, 11:59 PM IST | ✅ On Schedule |

---

## 2. Graph Data Model & Essential Cypher

All graph schemas, relationship directions, and traversal patterns are formally documented in [`docs/GRAPH_MODEL.md`](GRAPH_MODEL.md) and [`README.md`](../README.md#graph-model--domain-separation):

- **Canonical Dependency Direction:** `(caller:Module)-[:DEPENDS_ON]->(target:Module)`
  - Reverse impact traversal moves upstream to identify calling dependents.
- **Node Labels:** `Module`, `File`, `Person`, `Commit`, `PackageDependency`, `Vulnerability`, `SecurityFinding`, `Account`, `Device`, `Transaction`.
- **Relationship Types:** `DEPENDS_ON`, `CONTAINS`, `AUTHORED`, `TOUCHES`, `DECLARES_DEPENDENCY`, `AFFECTS`, `DETECTED_IN`, `OWNS`, `USES_DEVICE`, `SENDS_TO`.
- **Key Cypher Queries:**
  1. **Shortest Multi-Hop Path Traversal (2+ Hops):**
     ```cypher
     MATCH (src:Module {id: $src_id}), (tgt:Module {id: $tgt_id})
     WITH src, tgt, shortestPath((src)-[:DEPENDS_ON*]->(tgt)) AS p
     RETURN [n IN nodes(p) | n.id] AS path_nodes, length(p) AS hops
     ```
  2. **Reverse Impact Traversal (1–4 Hops):**
     ```cypher
     MATCH path = (caller:Module)-[:DEPENDS_ON*1..4]->(target:Module {id: $target_id})
     RETURN caller.id, caller.name, length(path) AS depth, [r IN relationships(path) | r.id] AS rel_ids
     ORDER BY depth ASC
     ```
  3. **PageRank Structural Centrality:**
     ```cypher
     CALL algo.pageRank('Module', 'DEPENDS_ON', {damping: 0.85, iterations: 20})
     YIELD node, score
     RETURN node.id AS module_id, node.name AS module_name, score
     ORDER BY score DESC LIMIT $top_k
     ```
  4. **Counterfactual Simulation with Safe Cloning:**
     ```cypher
     GRAPH.COPY nexusact_main scenario_sim_clone
     // Target excised in clone; impact evaluated; clone deleted in finally block
     GRAPH.DELETE scenario_sim_clone
     ```
  5. **Multi-Hop Financial Ring Traversal (Synthetic Fraud):**
     ```cypher
     MATCH path = (a:Account)-[:SENDS_TO*3..5]->(a)
     RETURN [n IN nodes(path) | n.id] AS ring_nodes, length(path) AS hops
     ```

---

## 3. Product Demonstrations (Judge Walkthrough)

Detailed demo steps and questions are available in [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

### 1. Codebase Impact & Multi-Hop Path Reasoning
- **Prompt:** *"Trace the path from the API router to graph storage client"*
- **Agent Action:** Auto-selects `nexusact_shortest_path` over MCP.
- **Graph Traversal:** 2 hops, 3 nodes: `backend.app.api.router` $\rightarrow$ `backend.app.api.endpoints.investigation` $\rightarrow$ `backend.app.graph.client`.
- **Canvas Experience:** Linear Investigation Path mode layout, directional glowing strokes, and breadcrumbs.

### 2. Panel Explanations Grounded in Evidence
- **All 10 Panels:** `graph`, `code`, `simulation`, `reviewers`, `trace`, `neighborhood`, `provenance`, `action`, `security`, `fraud`.
- Structured explanations with clear takeaways, findings, why it matters, evidence lists, limitations, and recommendations.
- SHA-256 hashed LRU cache.

### 3. Truthful Gemini Integration & Disclosed Fallback
- `GEMINI_ACTIVE` when configured with valid API key.
- `FALLBACK_ACTIVE` with 100% deterministic rule engine when key is absent.
- Transparent reporting across system status and investigation cards.

### 4. Dependency Vulnerability Security Triage (`nexusact_security_triage`)
- Real-time Google OSV.dev querying.
- Pinned dependency manifest coverage (`requirements.txt`, `package.json`).
- Honest disclosure of zero known advisories vs simulated test fixtures.

### 5. Isolated Synthetic Fraud Investigation (`nexusact_investigate_fraud`)
- Bounded to `nexusact_fraud_demo`.
- Detects 3-hop money redirection loop ($27,700) and shared device indicators.
- Benign control baseline accounts (`acc:201`, `acc:202`) verified as non-fraudulent.

### 6. Cryptographically Bound Action Execution
- Deterministic SHA-256 payload hash binding.
- Human-in-the-loop approval gate for GitHub issue generation.

---

## 4. Deployment & Judge Setup Options

Detailed platform trade-offs documented in [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).

### Option A: Local Judge-Ready Stack (Guaranteed Persistence & Speed)
```powershell
# Prerequisites: Docker Desktop, Python 3.12, Node.js 22
.\scripts\start.ps1

# Or with full production Docker containers:
docker compose -f docker-compose.prod.yml up --build -d
# Frontend: http://localhost:3000
# Backend: http://localhost:8000/api/health
```

### Option B: Free Cloud Hosting Strategy
- **Frontend:** Vercel / Render Static Site (`frontend/dist`)
- **Backend:** Render.com / Railway Web Service (binds dynamically to `$PORT`)
- **Graph Database:** FalkorDB Cloud Free tier (100MB RAM)
- *Honest Note:* FalkorDB Cloud Free tier deletes inactive databases after 14 days; local Docker Compose provides 100% reproducible persistence.

---

## 5. Quality Gate & Test Verification

| Suite | Status | Details |
|---|---|---|
| `ruff check .` | ✅ PASS | Python linting clean (0 errors) |
| `ruff format --check .` | ✅ PASS | Python formatting conforms |
| `mypy backend mcp_server` | ✅ PASS | Strict type checking passes (0 errors) |
| `pytest -q` | ✅ PASS | 146 unit, graph, and integration tests passing |
| `npm run lint` (frontend) | ✅ PASS | 0 warnings, 0 errors |
| `npm test -- --run` (frontend) | ✅ PASS | 20/20 Vitest tests passing (100% pass rate) |
| `npm run build` (frontend) | ✅ PASS | Clean production bundle generated |

---

## 6. AI Coding Assistant Disclosure

In adherence to the WeMakeDevs × FalkorDB hackathon rules:
- **Assistance Tools Used:** Google Antigravity IDE agentic coding workflows.
- **Scope of Use:** Pair programming, unit test generation, AST parser edge-case handling, and documentation scaffolding.
- **Human Author Oversight:** System architecture (GraphAction Fabric), FalkorDB Cypher schemas, security boundaries, cryptographic hash verification, and full manual validation were directed and verified by the repository owner.

---

## 7. Submission Checklist for Participant

- [x] Public GitHub repository: `https://github.com/VishwanathArchakMR/NexusAct.git`
- [x] Declared Track: *Agents That Act on Connected Data*
- [x] README with comprehensive setup and architectural overview
- [x] Graph schema and sample Cypher queries in README & docs
- [x] Truthful operational diagnostics replacing roadmap cards
- [x] Redesigned 3-column Code Inspector & Project Explorer
- [x] Dual-mode Graph Explorer (Investigation Path + Network Overview)
- [x] Persistent vertical navigation (Explore, Analyze, Evidence & Action, Workflows)
- [x] Evidence-grounded explanations across all 10 panels
- [x] Truthful Gemini & deterministic fallback reporting
- [x] Complete test suite passing locally (146 backend + 20 frontend)
- [ ] Record and attach 3-minute demo video walkthrough (using `docs/DEMO_SCRIPT.md`)
- [ ] Submit official form on WeMakeDevs portal before deadline
