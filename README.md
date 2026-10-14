# NexusAct (GraphAction Fabric)

[![FalkorDB](https://img.shields.io/badge/FalkorDB-v4.4.1-blue)](https://www.falkordb.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](https://fastapi.tiangolo.com/)
[![MCP](https://img.shields.io/badge/MCP-2.3.0-purple)](https://modelcontextprotocol.io/)
[![React](https://img.shields.io/badge/React-19.2-61dafb)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Strict-blue)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Application:** Engineering Brain  
> **Hackathon Track:** Agents That Act on Connected Data  
> **Status:** Phase 1 Foundation Verified & Operational

---

## 1. What is NexusAct?

**NexusAct** (GraphAction Fabric / GAF) is a graph-native AI engineering agent that understands repository relationships, simulates the blast radius of code changes in isolated graph branches, discovers domain-expert reviewers, verifies graph evidence paths, and acts safely on connected data.

Rather than treating the database as a decorative visualization tool, NexusAct uses **FalkorDB** as its computational core:
- **Graph-Powered Lineage:** Stores module dependency graphs, file structures, and contributor ownership.
- **Counterfactual Branching:** Uses FalkorDB's native `GRAPH.COPY` to clone the graph into an isolated scenario sandbox, test hypothetical deletions, and diff the blast radius before and after the modification.
- **Agent Action Engine:** Exposes typed, domain-specific tools via the Model Context Protocol (MCP).

---

## 2. What Works in Phase 1 vs. What is Planned for Phase 2

### Validated in Phase 1 (Foundation & Local Initialization)
- **Local FalkorDB v4.4.1** running via Docker with persistent volume storage (`nexusact_falkordb_data`).
- **Idempotent graph client & versioned schema initialization** (`Module`, `File`, `Person`, `Commit`).
- **Runtime-tested `GRAPH.COPY`** graph cloning and isolated scenario deletion.
- **Verified graph algorithms:** Native PageRank (`CALL algo.pageRank('Module', 'DEPENDS_ON')`) and Cypher `shortestPath(...)`.
- **FastAPI backend** with process liveness (`/api/v1/health`), honest readiness (`/api/v1/ready`), correlation IDs, structured logging, and strict CORS.
- **Restricted MCP server** (`mcp` v2.3.0) with typed contracts and read-only diagnostic tool (`nexusact_diagnose_graph`).
- **React 19 + TypeScript frontend** displaying live backend and FalkorDB connectivity.
- **Automated quality suite:** ruff lint/format, mypy type checks, 16 pytest tests, oxlint, vitest, and production build.

### Planned for Phase 2 (Real Graph Intelligence)
- Git AST parsing and full repository dependency ingestion.
- Multi-hop reverse-dependency impact algorithm (`trace_impact`).
- Contributor knowledge & reviewer discovery ranking (`who_knows`).
- Full counterfactual graph deletion & before/after diffing.
- Interactive graph explorer UI with scenario comparison.
- Autonomous GitHub issue generation from validated evidence.

---

## 3. Technology Stack & Versions Used

- **Operating System:** Windows 11 (with WSL2 container runtime)
- **Graph Database:** FalkorDB `v4.4.1` (pinned Docker image `falkordb/falkordb:v4.4.1`)
- **Python:** Python `3.12.8` managed with `uv` (`0.8.3`)
- **Backend Framework:** FastAPI `0.143.1`, Pydantic `2.14.1`, Uvicorn `0.54.0`
- **MCP Framework:** Python `mcp` SDK `2.3.0` (`MCPServer`)
- **Frontend:** React `19.2.8`, TypeScript `6.0.2`, Vite `8.3.4`, Lucide React `1.57.0`
- **Testing & Quality:** Pytest `9.1.1`, Ruff `0.17.0`, Mypy `2.4.0`, Oxlint `1.81.0`, Vitest `5.0.4`

---

## 4. Quick Start (Local Setup)

### Step 1: Clone and Initialize Configuration
```powershell
# Copy the verified environment configuration
Copy-Item .env.example .env
```

### Step 2: Run Automated Setup
```powershell
# Windows
.\scripts\setup.ps1

# Linux / macOS
chmod +x ./scripts/*.sh
./scripts/setup.sh
```

### Step 3: Start Services
```powershell
# Windows
.\scripts\start.ps1

# Linux / macOS
./scripts/start.sh
```

### Step 4: Verify Services
- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **FastAPI Interactive Docs:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **FastAPI Liveness Probe:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- **FastAPI Readiness Probe:** [http://127.0.0.1:8000/api/v1/ready](http://127.0.0.1:8000/api/v1/ready)

---

## 5. Testing and Validation

Run the complete, single-command quality pipeline:
```powershell
# Windows
.\scripts\check.ps1

# Linux / macOS
./scripts/check.sh
```

This automatically runs:
1. Python formatting & linting (`ruff`)
2. Python type checking (`mypy`)
3. Database capability & API test suite (`pytest`)
4. Frontend linting (`oxlint`)
5. Frontend component tests (`vitest`)
6. Frontend production build (`tsc -b && vite build`)

---

## 6. Architecture & Documentation Directory

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — System boundaries, components, and data flows.
- [docs/GRAPH_MODEL.md](docs/GRAPH_MODEL.md) — Graph schema conventions, stable IDs, and relationship directions.
- [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) — Step-by-step local workstation installation and execution.
- [docs/MCP_DESIGN.md](docs/MCP_DESIGN.md) — Tool registry, typed contracts, and stdio transport.
- [docs/SECURITY.md](docs/SECURITY.md) — Local security defaults, graph shields, and action boundaries.
- [docs/TESTING.md](docs/TESTING.md) — Capability test matrix, verified syntax, and limitations.
- [docs/DEPLOYMENT_PORTABILITY.md](docs/DEPLOYMENT_PORTABILITY.md) — Future cloud hosting considerations.
