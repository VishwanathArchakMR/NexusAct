# NexusAct — Hackathon Submission Checklist

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
  1. **Reverse Impact Traversal (1–4 Hops):**
     ```cypher
     MATCH path = (caller:Module)-[:DEPENDS_ON*1..4]->(target:Module {id: $target_id})
     RETURN caller.id, caller.name, length(path) AS depth, [r IN relationships(path) | r.id] AS rel_ids
     ORDER BY depth ASC
     ```
  2. **PageRank Structural Centrality:**
     ```cypher
     CALL algo.pageRank('Module', 'DEPENDS_ON', {damping: 0.85, iterations: 20})
     YIELD node, score
     RETURN node.id AS module_id, node.name AS module_name, score
     ORDER BY score DESC LIMIT $top_k
     ```
  3. **Counterfactual Simulation with Safe Cloning:**
     ```cypher
     GRAPH.COPY nexusact_main scenario_sim_clone
     // Target excised in clone; impact evaluated; clone deleted in finally block
     GRAPH.DELETE scenario_sim_clone
     ```
  4. **Multi-Hop Financial Ring Traversal (Synthetic Fraud):**
     ```cypher
     MATCH path = (a:Account)-[:SENDS_TO*3..5]->(a)
     RETURN [n IN nodes(path) | n.id] AS ring_nodes, length(path) AS hops
     ```

---

## 3. Product Demonstrations (Judge Walkthrough)

Detailed demo steps and prompts are available in [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

### Primary Track Demo: Codebase Impact Investigation
1. **Repository Context:** Select repository (`nexusact_main` or custom repo). Source SHA and git freshness verified.
2. **Project Explorer & Code Inspector:** Navigate live tree, view syntax-highlighted source, inspect AST symbol outline, and examine incoming/outgoing FalkorDB dependencies grounded in code.
3. **Agent Traversal:** Submit impact question: *"What components break if `backend/app/agent/planner.py` changes?"*
4. **Graph Explorer:** Visualize verified multi-hop dependency path in **Investigation Path View** and switch to **Network Overview**. Bidirectional jump between node and Code Inspector.
5. **Simulation & Action:** Execute counterfactual simulation (`GRAPH.COPY`), review affected modules, and inspect cryptographic action proposal (SHA-256 bound).

### Secondary Demo: Dependency Vulnerability Triage
1. Dynamic manifest inspection against public OSV records.
2. Traversal from external CVE to vulnerable package to internal consuming module.

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
| `mypy backend mcp_server` | ✅ PASS | Strict type checking passes |
| `pytest -q` | ✅ PASS | 136/136 unit and integration tests passing |
| `oxlint` (frontend) | ✅ PASS | 0 warnings, 0 errors |
| `vitest run` (frontend) | ✅ PASS | 18/18 tests passing (100% pass rate) |
| `tsc -b && vite build` | ✅ PASS | Clean production bundle generated |

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
- [x] Dual-mode Graph Explorer (Path View + Overview) with bidirectional sync
- [x] Repurposed Agent Investigation workspace
- [x] Coherent light/dark design system with high-contrast tokens
- [x] Complete test suite passing locally
- [ ] Record and attach 3-minute demo video walkthrough (using `docs/DEMO_SCRIPT.md`)
- [ ] Submit official form on WeMakeDevs portal before deadline
