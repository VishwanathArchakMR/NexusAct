# WeMakeDevs FalkorDB Graph Hacks — Submission Compliance Checklist

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Repository:** [https://github.com/VishwanathArchakMR/NexusAct](https://github.com/VishwanathArchakMR/NexusAct)  
**Track:** **Agents That Act on Connected Data**  
**Primary Graph Database:** FalkorDB v4.4.1  
**Submission Rules Reference:** [WeMakeDevs FalkorDB Hackathon Official Rules](https://www.wemakedevs.org/hackathons/falkordb/rules)  
**Date:** 2026-10-18  

---

## 1. Compliance Matrix

| Rule # | Requirement | Status | Evidence / In-Repository Verification |
| :--- | :--- | :---: | :--- |
| **Rule 2** | Open-source project hosted on GitHub with clear documentation and FalkorDB integration | **COMPLIANT** | Public repository with MIT License. Complete root [README.md](file:///c:/NexusAct/README.md), [ARCHITECTURE.md](file:///c:/NexusAct/docs/ARCHITECTURE.md), and FalkorDB v4.4.1 client integration in [backend/app/graph/client.py](file:///c:/NexusAct/backend/app/graph/client.py). |
| **Rule 3** | Original code written for the hackathon; no pre-existing closed code | **COMPLIANT** | Full Git commit history shows stepwise development of GraphAction Fabric (GAF) from initial commit to completion. |
| **Rule 6** | Accurate Track selection: **Agents That Act on Connected Data** | **COMPLIANT** | Explicitly stated across [README.md](file:///c:/NexusAct/README.md), [docs/ARCHITECTURE.md](file:///c:/NexusAct/docs/ARCHITECTURE.md), and UI header. Agent utilizes graph traversals, isolated counterfactual graph clones, and Cypher-grounded reasoning. |
| **Rule 10.1** | Public repository link on GitHub | **COMPLIANT** | Repository URL: `https://github.com/VishwanathArchakMR/NexusAct` |
| **Rule 10.2** | Complete README with setup instructions | **COMPLIANT** | Detailed in [README.md](file:///c:/NexusAct/README.md): Windows PowerShell, Linux/macOS, Docker Compose, virtual environment creation, FalkorDB bootstrap, backend, and frontend steps. |
| **Rule 10.3** | Documented Graph Data Model | **COMPLIANT** | Fully tabulated in [README.md](file:///c:/NexusAct/README.md#graph-data-model) and [docs/ARCHITECTURE.md](file:///c:/NexusAct/docs/ARCHITECTURE.md#3-graph-data-model--schema-specification). Covers codebase nodes (`Repository`, `Module`, `File`, `Person`, `Commit`), governance entities (`Investigation`, `ToolInvocation`, `Action`, `ActionOutcome`), and financial entities (`Account`, `Transaction`, `Device`, `IPAddress`, `Merchant`). |
| **Rule 10.4** | Cypher queries and graph algorithms | **COMPLIANT** | Documented with exact queries in [README.md](file:///c:/NexusAct/README.md#essential-cypher-queries--graph-algorithms): module resolution, bounded shortest path, upstream dependency impact, author commit expertise, counterfactual path comparison via `GRAPH.COPY`, circular transaction detection, and shared device clustering. |
| **Rule 10.5** | Working Demo Video | **ACTION REQUIRED BY AUTHOR** | A dedicated placeholder is established in [README.md](file:///c:/NexusAct/README.md#demonstration-video) (`<!-- DEMO VIDEO LINK PLACEHOLDER -->`). The author will record the walkthrough using the script in [docs/FINAL_DEMO_CHECKLIST.md](file:///c:/NexusAct/docs/FINAL_DEMO_CHECKLIST.md) and insert the URL. |
| **Rule 10.6** | Live deployment OR complete local setup instructions | **COMPLIANT** | Step-by-step local setup instructions verified. Production deployment topology for Oracle Cloud Always Free Ampere A1 (or AMD64 equivalent) prepared in [docs/DEPLOYMENT_PLAN.md](file:///c:/NexusAct/docs/DEPLOYMENT_PLAN.md) and [docker-compose.prod.yml](file:///c:/NexusAct/docker-compose.prod.yml). |
| **Rule 11** | Disclosure of AI coding assistants | **COMPLIANT** | Explicitly disclosed in [README.md](file:///c:/NexusAct/README.md#responsible-disclosure--ai-assistant-usage). |
| **Rule 12** | Plagiarism prevention & originality | **COMPLIANT** | Entire codebase, GraphAction Fabric architecture, ephemeral clone simulation algorithms, and AST graph parsing are original implementations. |
| **Rule 13** | Author comprehension of graph model, architecture, and code | **COMPLIANT** | Architecture, design rationale, Cypher optimization, and safety gates are thoroughly documented to enable authoritative author defense during judging. |

---

## 2. Key Graph Differentiators for Judges

1. **FalkorDB is the Primary Reasoning Engine, Not Just a Visualization Store:**
   - LLMs suffer from severe hallucinations when analyzing multi-hop architectural dependencies. NexusAct queries FalkorDB v4.4.1 dynamically for dynamic schema discovery, bounded shortest path traversals, and Cypher-grounded evidence.
2. **Counterfactual Dependency Simulation via Ephemeral Graph Clones:**
   - Instead of mutating the live production graph or doing superficial AST string diffs, NexusAct leverages FalkorDB's native `GRAPH.COPY` to create an ephemeral, fully isolated sandbox graph (`scen_<uuid>`). It severs the candidate module, measures disrupted and surviving paths, and drops the clone with `GRAPH.DELETE`, leaving the primary graph 100% pristine.
3. **Model Context Protocol (MCP) Server Integration:**
   - NexusAct exposes its graph tools through the official Model Context Protocol (`mcp v2.3`) standard, enabling any MCP-compliant agent or client to invoke graph tools like `trace_dependency_impact`, `who_knows`, and `simulate_removal`.
4. **Human-in-the-Loop Safe Action Execution:**
   - Actions (such as filing GitHub remediation issues) require strict human verification with a canonical SHA-256 payload hash lock. Even if an LLM is compromised or hallucinates, actions cannot be modified between proposal and execution.
5. **Cross-Domain Graph Isolation:**
   - Codebase graphs (`repo_*`), financial transaction graphs (`fin_*`), and scenario clones (`scen_*`) reside in isolated graph namespaces, preventing cross-domain schema or data leakage.

---

## 3. Remaining Manual Tasks for the Author

Before submitting on the WeMakeDevs hackathon portal:

1. **Record the Demo Video:**
   - Follow the 3-minute demonstration script in [docs/FINAL_DEMO_CHECKLIST.md](file:///c:/NexusAct/docs/FINAL_DEMO_CHECKLIST.md).
   - Upload to YouTube (Public or Unlisted) or Loom.
   - Replace the `<!-- DEMO VIDEO LINK PLACEHOLDER -->` in [README.md](file:///c:/NexusAct/README.md) with the actual link.
2. **Review Deployment or Local Instructions:**
   - If hosting publicly before deadline, execute the verified deployment steps in [docs/DEPLOYMENT_PLAN.md](file:///c:/NexusAct/docs/DEPLOYMENT_PLAN.md).
   - If submitting local setup, verify that judges can clone and run `docker compose -f docker-compose.prod.yml up` or the native local setup.
3. **Submit on Platform:**
   - Enter repository URL, demo video URL, deployment URL (or mention local reproduction), and track: **Agents That Act on Connected Data**.
