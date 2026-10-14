# NexusAct (GraphAction Fabric) — Architecture Specification

## 1. Executive Summary

**NexusAct** (GraphAction Fabric / GAF) is a graph-native engineering agent designed to investigate codebase relationships, evaluate reverse-dependency impact across modules, discover domain-expert reviewers, perform isolated counterfactual scenario simulations on connected data, and execute verified actions.

NexusAct operates in the hackathon track: **Agents That Act on Connected Data**.

## 2. Core Architectural Principle

FalkorDB is our single primary database and performs essential product work. The graph holds both the static codebase topology and dynamic operational records (investigations, scenario forks, evidence references, action outcomes). We strictly reject dual-database architectures, transactional outboxes, or vector-database workarounds for Phase 1.

```
+-----------------------------------------------------------------------+
|                             USER / DEVELOPER                          |
+-----------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                REACT FRONTEND (TypeScript + Vite, Port 5173)          |
|  - System Health & Telemetry Dashboard                                |
|  - Real-time Backend & FalkorDB Status                                |
+-----------------------------------------------------------------------+
                                    |
                                    | REST (JSON / CORS restricted)
                                    v
+-----------------------------------------------------------------------+
|               FASTAPI BACKEND (Python 3.12, Port 8000)                |
|  - Lifespan Graph Initialization                                      |
|  - Request Correlation ID Middleware                                  |
|  - Structured Logging & Central Settings (Pydantic)                   |
|  - /api/v1/health (Liveness) & /api/v1/ready (Readiness)              |
+-----------------------------------------------------------------------+
                 |                                      |
                 | Cypher / TCP 6379                    | Stdio / RPC
                 v                                      v
+----------------------------------+   +--------------------------------+
|       FALKORDB GRAPH ENGINE      |   |       NEXUSACT MCP SERVER      |
|    (Docker Compose, Port 6379)   |   |     (mcp 2.x, Stdio Transport) |
|  - Primary Graph: nexusact_main  |   |  - Tool: nexusact_diagnose_    |
|  - Volume: nexusact_falkordb_data|   |    graph                       |
|  - GRAPH.COPY Scenario Branching |   |  - Restricted Read-Only Safety |
|  - Algorithms: PageRank, Cypher  |   +--------------------------------+
|    ShortestPath                  |
+----------------------------------+
```

## 3. Component Boundaries

### 3.1 Frontend Service (`frontend/`)
- **Technology:** React 19, TypeScript strict mode, Vite, Lucide React icons.
- **Role:** Developer dashboard showing real live connectivity and telemetry.
- **Safety Boundary:** The frontend never connects directly to the database. All requests are routed through the backend API.

### 3.2 Backend Service (`backend/`)
- **Technology:** FastAPI, Pydantic v2, Uvicorn, FalkorDB Python Client.
- **Role:** Central business logic coordinator, schema migration manager, health monitor.
- **Endpoints:**
  - `GET /api/v1/health`: Process liveness probe.
  - `GET /api/v1/ready`: Database readiness probe verifying FalkorDB connectivity.
  - `GET /api/v1/system/status`: Aggregate telemetry for frontend.

### 3.3 FalkorDB Database (`docker-compose.yml`)
- **Technology:** FalkorDB official Docker image (`falkordb/falkordb:v4.4.1`).
- **Storage:** Dedicated named persistent volume `nexusact_falkordb_data` mounted at `/data`.
- **Networking:** Localhost binding (`127.0.0.1:6379`) prevents public network exposure.
- **Counterfactual Engine:** `GRAPH.COPY` clones source graph branches into ephemeral scenario graphs.

### 3.4 MCP Server (`mcp_server/`)
- **Technology:** Python `mcp` SDK (v2.x `MCPServer`).
- **Transport:** Standard input/output (stdio) with all diagnostics logged to standard error (`stderr`).
- **Tool Registry:** Strict classification of tools into `READ_ONLY`, `MUTATING`, or `DESTRUCTIVE`.

## 4. Phase 1 Boundaries (What is Intentionally Deferred)
Phase 1 delivers the tested foundation. The following intelligence features are intentionally deferred to Phase 2:
- Git AST parsing and full repository ingestion.
- Multi-hop reverse-dependency impact algorithm (`trace_impact`).
- Contributor knowledge & reviewer discovery ranking (`who_knows`).
- LLM agent orchestration loop and autonomous scenario planning.
- GitHub API issue creation and write-back.
