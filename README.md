# NexusAct — Graph-Native AI That Investigates, Simulates, and Acts

[![NexusAct CI](https://github.com/VishwanathArchakMR/NexusAct/actions/workflows/ci.yml/badge.svg)](https://github.com/VishwanathArchakMR/NexusAct/actions/workflows/ci.yml)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-v4.4.1-0080FF?logo=redis)](https://www.falkordb.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript)](https://www.typescriptlang.org/)
[![MCP](https://img.shields.io/badge/MCP-v2.3.0-8A2BE2)](https://modelcontextprotocol.io/)
[![Live Deployment](https://img.shields.io/badge/Live%20Gateway-Online-brightgreen)](https://gateway-production-27a8.up.railway.app/)

> **FalkorDB Graph Hacks Hackathon Submission**  
> **Track:** **Agents That Act on Connected Data**  
> **Primary Graph Database:** FalkorDB v4.4.1 (Low-Latency Redis Protocol / Cypher Engine)  
> **Architecture:** GraphAction Fabric (GAF)  
> **Live Production Gateway:** **[https://gateway-production-27a8.up.railway.app/](https://gateway-production-27a8.up.railway.app/)**  
> **Repository:** [https://github.com/VishwanathArchakMR/NexusAct](https://github.com/VishwanathArchakMR/NexusAct)

---

## 1. Project Overview & The Problem

Software systems, vulnerability propagation paths, code author networks, and financial transaction streams are inherently **connected graphs**. Yet conventional AI coding and security assistants treat codebases as flat text embeddings or keyword indices. When queried about architectural blast radii, author expertise, or cascading dependencies, standard LLMs suffer from severe hallucinations—inventing nonexistent imports, missing multi-hop relationships, and proposing unverified changes.

**NexusAct** solves this by establishing **FalkorDB v4.4.1** as the central, deterministic reasoning engine for autonomous AI agents.

Rather than relying on flat vector similarity, NexusAct models code structures, Git revision histories, security advisories, and financial transaction topologies as rich property graphs. When a user asks an architectural question, initiates an impact simulation, or investigates a fraud ring, NexusAct dynamically queries FalkorDB using Cypher, performs multi-hop path traversals, runs counterfactual simulations in isolated sandbox clones, and returns answers strictly grounded in verified graph evidence.

---

## 2. Track Alignment: Agents That Act on Connected Data

NexusAct is designed specifically for the **Agents That Act on Connected Data** track:

1. **FalkorDB as the Primary Reasoning Engine:**  
   FalkorDB is not merely a data store backing a visualization; it is the core analytical substrate. Schema discovery, shortest path traversals, PageRank centrality, dependency reachability, and contributor rankings are computed natively in FalkorDB via Cypher queries and graph algorithms.
2. **Counterfactual Simulation via Ephemeral Graph Clones:**  
   To evaluate the blast radius of removing or refactoring a module without risking production data, NexusAct uses FalkorDB's native `GRAPH.COPY` command to create an ephemeral sandbox clone (`scen_<uuid>`). It excises the candidate module in the sandbox, computes severed versus surviving paths, and drops the clone with `GRAPH.DELETE`—leaving the primary graph 100% untouched.
3. **Model Context Protocol (MCP v2.3.0) Tool Exposure:**  
   Graph reasoning primitives (`trace_impact`, `who_knows`, `simulate_removal`, `security_triage`, `detect_cycles`) are exposed through standard MCP tools, enabling any MCP-compliant agent or client to act directly on connected graph data.
4. **Graph-Grounded AI Assistant with Verifiable Evidence:**  
   The Graph AI Chat assistant queries FalkorDB dynamically for schema labels and relationships, constructs bounded read-only Cypher queries, validates them against mutation injection, and synthesizes answers that cite concrete nodes, paths, and millisecond query execution traces.
5. **Human-in-the-Loop Cryptographic Action Gating:**  
   When the agent proposes an external remediation action (such as filing a GitHub issue), it calculates a canonical SHA-256 hash of the proposal. External execution requires explicit human review and cryptographic hash verification to prevent the execution of tampered or hallucinated payloads.
6. **Strict Domain & Namespace Isolation:**  
   Codebase repositories (`nexusact_main`, `repo_*`), financial transaction callsets (`fin_*`), and scenario simulations (`scen_*`) reside in strictly segregated FalkorDB graphs, preventing cross-domain schema or data leakage.

---

## 3. Core Features

| Feature | Description | Graph Implementation & Evidence Used |
| :--- | :--- | :--- |
| **Repository Ingestion** | Ingests public GitHub repositories (via shallow clone) or uploaded local Git `.zip` archives into isolated FalkorDB graphs. | Parses AST modules, files, imports, and Git commit histories. Stores as `(:Repository)-[:CONTAINS]->(:Module)`. Bounded by size (100 MB) and timeout limits. |
| **Interactive Software Graph** | 2D visual canvas rendering modules, files, packages, and contributors with interactive node-type coloring, physics layout, and dynamic filtering. | Traverses `MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 80` in the active repository graph. |
| **Codebase Walkthrough & AST Inspector** | Source-aware code browser with directory hierarchy, syntax highlighting, and bidirectional navigation from graph nodes to physical source lines. | Resolves `m.path` against the active repository snapshot, parsing function/class symbol outlines with exact line ranges. |
| **Change Impact & Reviewers** | Measures upstream caller blast radius and recommends domain experts for any target module based on Git commit activity. | Traverses reverse dependencies `(caller)-[:DEPENDS_ON*1..4]->(target)` and commit authorship `(:Person)-[:AUTHORED]->(:Commit)-[:TOUCHES]->(:File)`. |
| **Security & Vulnerability Triage** | Correlates package dependencies against OSV.dev advisories and traces reachability to internal code modules. | Traverses `(:Module)-[:REQUIRES_PACKAGE]->(:PackageDependency)-[:HAS_VULNERABILITY]->(:Vulnerability)`. |
| **Counterfactual Scenario Simulation** | Excises candidate modules and measures architectural blast radius across upstream callers. | Uses `GRAPH.COPY` to clone into `scen_*`, executes `DETACH DELETE`, compares before/after reachability, and cleans up with `GRAPH.DELETE`. Truthfully reports zero impact for leaves. |
| **Graph AI Chat (Right-Side Drawer)** | Context-aware AI assistant bound to the active repository or financial dataset. Generates read-only Cypher, executes it in FalkorDB, and returns evidence-grounded answers. | Powered by Google Gemini 2.5 Flash when configured; falls back gracefully to deterministic graph templates if unconfigured. Strictly blocks mutating Cypher statements. |
| **Financial Fraud Investigation** | Ingests transaction datasets into isolated graphs, detecting 3- to 5-hop circular routing loops and shared device/IP infrastructure. | Traverses `(:Account)-[:SENDS_TO*3..5]->(:Account)` and `(:Account)-[:USES_DEVICE]->(:Device)`. Features a transparently labeled synthetic AML benchmark. Risk scores are investigative signals, not legal findings. |
| **Source Provenance & Freshness Engine** | Binds every investigation to an authoritative `SourceSnapshot` containing the exact Git commit SHA, graph name, and working-tree fingerprint. | Compares working-tree fingerprints and commit SHAs to verify freshness before executing investigations. |

---

## 4. System Architecture

```mermaid
flowchart TD
    subgraph Frontend["React 19 Frontend (TypeScript + Vite)"]
        UI["NexusAct Workspace"]
        Drawer["Graph AI Chat Drawer (Right-Side)"]
        SimPanel["Scenario Simulation Panel"]
        RevPanel["Reviewers & Authors Panel"]
        CodePanel["Code Inspector & AST Tree"]
        FraudPanel["Financial Fraud Investigation"]
    end

    subgraph Ingress["Production Ingress & Reverse Proxy"]
        Gateway["Production HTTP Gateway (:80 / :443)"]
    end

    subgraph Backend["FastAPI Backend Service (:8000)"]
        Router["API Router (/api/v1)"]
        Registry["Trusted Source & Dataset Registry"]
        ChatService["GraphChatService"]
        AgentLoop["Adaptive Investigation Agent"]
        SimEngine["Scenario Simulation Engine"]
        IngestEngine["AST & Git Ingestion Pipeline"]
        FinanceEngine["Financial Normalization & Ingestion"]
        ActionService["Verified Action Service (SHA-256 Lock)"]
    end

    subgraph LLM_Subsystem["LLM Planning & Grounding"]
        Provider["Google Gemini 2.5 Flash / Deterministic Fallback"]
        CypherValidator["Read-Only Cypher Safety Validator"]
    end

    subgraph FalkorDB_Engine["FalkorDB Graph Database (:6379)"]
        BaseGraph[("Base Graph:\nnexusact_main / repo_*")]
        EphemeralClone[("Ephemeral Scenario Clone:\nscen_<uuid>")]
        FinGraph[("Isolated Financial Graph:\nfin_<dataset_id>")]
    end

    subgraph Ext_Tools["External Services & MCP"]
        MCP["Model Context Protocol Server (mcp v2.3.0)"]
        OSV["OSV.dev Vulnerability API"]
        GitRemote["GitHub API (Human-Approved Issues)"]
    end

    %% Ingress & Routing
    Frontend -.->|Relative /api/v1/*| Gateway
    Gateway -->|Reverse Proxy| Router

    %% User Interactions
    Router --> ChatService
    Router --> SimEngine
    Router --> IngestEngine
    Router --> FinanceEngine
    Router --> ActionService
    Router --> AgentLoop

    %% Source Registry Resolution
    ChatService --> Registry
    SimEngine --> Registry
    FinanceEngine --> Registry
    Registry -.->|Authoritative Graph Name & Revision| FalkorDB_Engine

    %% Graph AI Chat Grounded Lifecycle
    ChatService -->|1. Request Dynamic Schema| BaseGraph
    BaseGraph -->|2. Labels & Rel Types| ChatService
    ChatService -->|3. Question + Schema Prompt| Provider
    Provider -->|4. Generate Cypher Query| CypherValidator
    CypherValidator -->|5. Block Mutations / Verify Read-Only| BaseGraph
    BaseGraph -->|6. Real Evidence Rows & Paths| ChatService
    ChatService -->|7. Grounded Answer Prompt + Evidence| Provider
    Provider -->|8. Natural Language Synthesis| ChatService
    ChatService -->|9. Answer + Trace + Evidence Chips| Drawer

    %% Scenario Simulation Isolation Flow
    SimEngine -->|1. GRAPH.COPY BaseGraph EphemeralClone| BaseGraph
    BaseGraph --> EphemeralClone
    SimEngine -->|2. DETACH DELETE Target Module| EphemeralClone
    EphemeralClone -->|3. Measure Severed & Surviving Paths| SimEngine
    SimEngine -->|4. GRAPH.DELETE EphemeralClone| EphemeralClone
    SimEngine -->|5. Base Graph 100% Preserved| BaseGraph

    %% Agent Loop and MCP
    AgentLoop --> MCP
    MCP --> OSV
    MCP --> BaseGraph

    %% Action Verification
    ActionService -->|SHA-256 Hash Verified| GitRemote
```

### The Graph-Driven Investigation Lifecycle
```
Source (GitHub URL / ZIP) 
  → Validate (URL format, size & traversal guards)
  → Ingest (AST parsing & Git history extraction)
  → Build Graph (FalkorDB idempotent MERGE)
  → Query Evidence (Multi-hop Cypher traversals)
  → Investigate (Agent planning & MCP tool selection)
  → Explain Findings (Grounding with real node/path citations)
```

---

## 5. Graph Data Model & Cypher Reasoning

NexusAct partitions data into isolated graph namespaces:

### 5.1 Software Engineering Graph (`nexusact_main`, `repo_<repo_id>`)

| Node Label | Key Properties | ID Convention / Description |
| :--- | :--- | :--- |
| `Repository` | `id`, `name`, `url_or_path`, `commit_sha`, `source_type` | Root container for the codebase snapshot. |
| `Module` | `id`, `name`, `path`, `language`, `loc` | Granular architectural component or logical module (`mod:<clean_path>`). |
| `File` | `id`, `path`, `extension`, `size_bytes` | Physical file on disk (`file:<path>`). |
| `Person` | `id`, `name`, `email` | Contributor, author, or reviewer (`person:<email>`). |
| `Commit` | `id`, `sha`, `message`, `timestamp` | Git commit history changeset (`commit:<sha>`). |
| `PackageDependency` | `id`, `name`, `version`, `ecosystem` | Third-party dependency declared in package manifests. |
| `Vulnerability` | `id`, `osv_id`, `summary`, `severity`, `fixed_version` | Known security vulnerability advisory. |
| `Investigation` | `id`, `query`, `status`, `created_at` | Agent investigation session tracking. |
| `ToolInvocation` | `id`, `tool_name`, `parameters`, `duration_ms` | Audit record of an executed MCP tool. |
| `Action` | `id`, `title`, `body`, `status`, `approved_payload_hash` | Human-gated remediation proposal. |

#### Canonical Software Relationships
- `(:Module)-[:DEPENDS_ON]->(:Module)`: **Canonical dependency direction** (`caller -DEPENDS_ON-> dependency`).
- `(:Module)-[:CONTAINS]->(:File)`: Module to physical disk file linkage.
- `(:Person)-[:AUTHORED]->(:Commit)`: Contributor commit authorship.
- `(:Commit)-[:TOUCHES]->(:File)`: Files modified in a commit changeset.
- `(:Module)-[:REQUIRES_PACKAGE]->(:PackageDependency)`: Third-party package requirement.
- `(:PackageDependency)-[:HAS_VULNERABILITY]->(:Vulnerability)`: Reachable vulnerability binding.

### 5.2 Financial Fraud Graph (`fin_<dataset_id>`)

| Node Label | Key Properties | Description |
| :--- | :--- | :--- |
| `Account` | `id`, `account_number`, `holder_name`, `risk_score` | Financial entity or bank account. |
| `Transaction` | `id`, `tx_id`, `amount`, `currency`, `timestamp` | Monetary transfer record. |
| `Device` | `id`, `device_id`, `device_type` | Hardware or browser fingerprint. |
| `IPAddress` | `id`, `ip_address`, `asn`, `country` | Network client IP address. |

#### Canonical Financial Relationships
- `(:Account)-[:SENDS_TO {amount, timestamp, tx_id}]->(:Account)`: Directed monetary transaction.
- `(:Account)-[:USES_DEVICE]->(:Device)`: Hardware fingerprint binding.
- `(:Account)-[:LOGS_FROM_IP]->(:IPAddress)`: Network client binding.

### 5.3 Essential Cypher Queries

Every query executed by NexusAct is validated, bounded, and tuned for FalkorDB v4.4.1:

#### 1. Upstream Dependency Blast Radius
```cypher
MATCH (target:Module {name: $module_name})
MATCH (caller:Module)-[:DEPENDS_ON*1..4]->(target)
RETURN DISTINCT caller.name AS dependent_module, caller.path AS file_path
LIMIT 50
```

#### 2. Contributor Expertise From Commit History
```cypher
MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:TOUCHES]->(f:File)<-[:CONTAINS]-(m:Module {name: $module_name})
RETURN p.name AS author_name,
       p.email AS author_email,
       count(DISTINCT c) AS commit_count,
       count(DISTINCT f) AS files_touched,
       max(c.timestamp) AS latest_commit
ORDER BY commit_count DESC
LIMIT 10
```

#### 3. Counterfactual Path Comparison via Native `GRAPH.COPY`
```cypher
-- Step 1: Duplicate active graph to ephemeral sandbox
GRAPH.COPY nexusact_main scen_550e8400

-- Step 2: Sever candidate module in sandbox
GRAPH.QUERY scen_550e8400 "MATCH (m:Module {name: 'auth_service'}) DETACH DELETE m"

-- Step 3: Compute surviving vs severed paths in sandbox
GRAPH.QUERY scen_550e8400 "MATCH (c:Module)-[:DEPENDS_ON]->(dep:Module) RETURN count(*)"

-- Step 4: Drop ephemeral sandbox, leaving primary graph 100% untouched
GRAPH.DELETE scen_550e8400
```

#### 4. Multi-Hop Circular Financial Routing (3–5 Hops)
```cypher
MATCH path = (a:Account)-[:SENDS_TO*3..5]->(a)
WHERE all(i in range(0, length(path)-2) WHERE (nodes(path)[i]) <> (nodes(path)[i+1]))
RETURN [n in nodes(path) | n.id] AS cycle_accounts,
       [r in relationships(path) | r.amount] AS amounts,
       length(path) AS cycle_length
LIMIT 20
```

---

## 6. Technology Stack

| Layer | Technologies & Supported Versions | Role in NexusAct |
| :--- | :--- | :--- |
| **Graph Database** | **FalkorDB v4.4.1** | Core low-latency graph reasoning engine, Cypher query execution, `GRAPH.COPY` ephemeral sandboxes. |
| **Backend API** | **Python 3.12+**, **FastAPI 0.115+**, **Uvicorn** | REST API routing, AST parsing, Git history extraction, graph query execution. |
| **Data Validation** | **Pydantic v2** | Strict input/output schema validation and contract models. |
| **Tool Protocol** | **Model Context Protocol (`mcp` v2.3.0)** | Standardized agent-to-tool interface exposing graph reasoning primitives. |
| **AI Planning** | **Google Gemini 2.5 Flash** (`google-genai`) | Context-grounded Cypher query generation and natural language synthesis. |
| **Deterministic Engine** | Built-in Cypher template planner | Fully functional zero-hallucination fallback when no LLM API key is configured. |
| **Frontend UI** | **React 19**, **TypeScript 5.9**, **Vite 6** | Interactive 2D graph canvas, Code Inspector, simulation controls, and audit views. |
| **Containerization** | **Docker 27+**, **Docker Compose v2** | Containerized deployment for FalkorDB and the FastAPI backend. |
| **Code Quality** | **Ruff**, **MyPy (Strict)**, **Pytest**, **Vitest** | Automated linting, static type checking, and unit/integration testing suites. |

---

## 7. Getting Started Locally

### Prerequisites
- **Git** (2.30+)
- **Docker & Docker Compose** (for running FalkorDB)
- **Python 3.12+**
- **Node.js 22+ & npm**

### Step-by-Step Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/VishwanathArchakMR/NexusAct.git
cd NexusAct
```

#### 2. Start FalkorDB
```bash
# Start FalkorDB v4.4.1 in background
docker compose up -d falkordb

# Verify FalkorDB is healthy
docker compose ps
```

#### 3. Configure Backend Environment
```bash
# Copy template environment file
cp .env.example .env
```

Key environment configuration variables:
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Set to `development` for local debug, or `production` for strict mode. |
| `FALKORDB_HOST` | `127.0.0.1` | Host where FalkorDB is listening. |
| `FALKORDB_PORT` | `6379` | FalkorDB port. |
| `FALKORDB_PRIMARY_GRAPH` | `nexusact_main` | Primary graph name. |
| `LLM_PROVIDER` | `gemini` | `gemini` or `none` (deterministic Cypher fallback). |
| `GEMINI_API_KEY` | *(Optional)* | Google AI Studio API key. If omitted, NexusAct operates in deterministic fallback mode. |
| `PUBLIC_DEMO_MODE` | `false` | Set to `false` for unrestricted local development. |

#### 4. Install Backend Dependencies & Start Server
```powershell
# Windows PowerShell:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install uv
uv pip install -e ".[dev]"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
```bash
# Linux / macOS Bash:
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv pip install -e ".[dev]"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5. Install Frontend Dependencies & Start Development Server
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```

#### 6. Access Local Application & Documentation
- **NexusAct Web Workspace:** `http://localhost:5173`
- **Backend Liveness Health:** `http://localhost:8000/health` (`{"status":"OK"}`)
- **Backend Readiness Probe:** `http://localhost:8000/ready` (`{"status":"READY","falkordb":"CONNECTED"}`)
- **Interactive Swagger API Docs:** `http://localhost:8000/api/docs`
- **OpenAPI Schema:** `http://localhost:8000/api/openapi.json`

#### 7. Stopping Services Safely
```bash
# Stop backend and frontend by pressing Ctrl+C in their respective terminals
# Stop FalkorDB container while preserving data volume:
docker compose down
```

---

## 8. Exploring the Live Demo

The production application is live at:  
👉 **[https://gateway-production-27a8.up.railway.app/](https://gateway-production-27a8.up.railway.app/)**

### Guided Walkthrough for Hackathon Judges

1. **Explore the Preloaded Graph:**  
   The workspace opens to the preloaded `NexusAct` codebase graph. Examine the visual node clusters, hover over modules to see connectivity, and filter by node types.
2. **Onboard a Public GitHub Repository:**  
   Click **+ Onboard Repo** → select **Public GitHub URL** → enter an eligible public repository (e.g. `https://github.com/VishwanathArchakMR/AletheiaOS`) → click **Ingest Repository**.  
   Watch the progress bar as FalkorDB indexes the repository into an isolated graph namespace (`repo_<owner>_<repo>`).
3. **Upload a Local Git Repository Archive:**  
   Click **+ Onboard Repo** → select **Upload Local Git Repo (.zip)** → select any repository `.zip` archive (up to 50 MB) → click **Upload & Ingest Archive**.
4. **Inspect Source & Symbols in Code Inspector:**  
   Open the **Code Inspector** panel. Browse the directory tree, view source files with syntax highlighting, and click symbol outline entries to highlight exact AST function or class definitions.
5. **Run an Adaptive Investigation:**  
   In the **Software Graph** view, select a target module and click **Investigate** (or ask a natural language question in the prompt). Review the step-by-step tool plan, FalkorDB Cypher execution trace, and evidence-grounded findings.
6. **Execute a Counterfactual Scenario Simulation:**  
   Switch to **Scenario Simulation**. Select a candidate module from the dropdown and click **Simulate Removal**. Observe the side-by-side comparison of surviving versus severed dependencies computed inside an ephemeral `GRAPH.COPY` sandbox clone.
7. **Evaluate Domain Expertise & Reviewers:**  
   Open **Reviewers & Authors** to see weighted contributor rankings derived from commit history and file touch frequency.
8. **Inspect Financial Fraud Rings:**  
   Navigate to the **Fraud Investigation** view. Select the preloaded benchmark dataset to view detected 3- to 5-hop circular routing loops and shared device/IP identity clusters.

> **Note on Public Demo Safeguards:**  
> The live deployment runs with `PUBLIC_DEMO_MODE=true` to ensure zero-cost infrastructure stability. Direct arbitrary local filesystem paths cannot access a visitor's computer (use the ZIP upload feature instead). External GitHub write actions and financial modifications are safely gated.

---

## 9. API & Developer Reference

FastAPI routes are organized modularly under the `/api/v1` prefix:

### Endpoint Overview

| Category | Route | Method | Description |
| :--- | :--- | :--- | :--- |
| **Health & Diagnostics** | `/health` | `GET` | Container liveness check. |
| | `/ready` | `GET` | Database readiness check verifying FalkorDB connectivity. |
| | `/api/v1/system/status` | `GET` | Full diagnostic telemetry (graph name, node count, schema version). |
| **Repository Ingestion** | `/api/v1/ingest/clone-and-ingest` | `POST` | Ingests a public GitHub repository with size and rate limits. |
| | `/api/v1/ingest/upload-zip` | `POST` | Extracts and ingests an uploaded repository `.zip` archive. |
| | `/api/v1/ingest/repositories` | `GET` | Lists all registered and ingested repositories. |
| | `/api/v1/ingest/snapshot/{repo_id}` | `GET` | Returns authoritative `SourceSnapshot` with commit SHA and graph. |
| | `/api/v1/ingest/file-tree` | `GET` | Retrieves directory hierarchy bounded by depth and limit. |
| | `/api/v1/ingest/file-content` | `GET` | Retrieves file source lines, symbol outlines, and graph linkage. |
| **Investigation & Planning** | `/api/v1/investigate` | `POST` | Primary adaptive multi-step investigation loop across graph. |
| | `/api/v1/investigation/run` | `POST` | Executes investigation agent with budget and mode parameters. |
| | `/api/v1/investigation/chat` | `POST` | Graph AI Assistant conversational endpoint with Cypher trace. |
| | `/api/v1/investigation/explain-panel`| `POST` | Structured evidence explanation for a specific workspace panel. |
| **Graph Analysis Tools** | `/api/v1/investigation/tools/trace-impact` | `POST` | Reverse dependency impact analysis up to 4 hops. |
| | `/api/v1/investigation/tools/who-knows` | `POST` | Contributor expertise and reviewer scoring. |
| | `/api/v1/investigation/tools/simulate` | `POST` | Counterfactual module removal simulation via `GRAPH.COPY`. |
| | `/api/v1/investigation/tools/security-triage` | `POST` | OSV vulnerability correlation and reachability tracing. |
| **Financial Investigation** | `/api/v1/finance/datasets` | `GET` | Lists available financial transaction graphs. |
| | `/api/v1/finance/investigate` | `POST` | Detects circular routing cycles and shared infrastructure. |
| **Action Execution** | `/api/v1/action/propose` | `POST` | Generates structured remediation proposal with SHA-256 lock. |
| | `/api/v1/action/execute` | `POST` | Executes human-approved proposal verifying SHA-256 hash match. |

### API Documentation Links
- **OpenAPI 3.1 JSON Specification:**  
  Live Gateway: [https://gateway-production-27a8.up.railway.app/api/openapi.json](https://gateway-production-27a8.up.railway.app/api/openapi.json)  
  Local Development: `http://localhost:8000/api/openapi.json`
- **Interactive Swagger UI:**  
  Local Development: `http://localhost:8000/api/docs`  
  *(Note: Interactive Swagger documentation is disabled in production to minimize attack surface).*

### Internal Documentation Index
- [System Architecture](docs/ARCHITECTURE.md)
- [Graph Data Model & Cypher Schemas](docs/GRAPH_MODEL.md)
- [Model Context Protocol (MCP) Design](docs/MCP_DESIGN.md)
- [Local Development & Setup Guide](docs/LOCAL_SETUP.md)
- [Security Defaults & Action Boundaries](docs/SECURITY.md)
- [Cloud Deployment Guide](docs/DEPLOYMENT.md)

---

## 10. Security, Provenance & Limitations

### Public Demo Protections (`PUBLIC_DEMO_MODE=true`)
1. **GitHub URL Validation:** Enforces strict HTTPS GitHub URLs with valid alphanumeric owner and repository patterns.
2. **Resource Boundaries:** Maximum 100 MB repository size preflight check, shallow clone (`depth=1`), and 90-second timeout.
3. **ZIP Upload Sanitization:** 50 MB maximum archive size, memory stream inspection, and zip-slip path traversal prevention (`_safe_extract_zip`).
4. **Rate Limiting & Concurrency Semaphore:** In-memory sliding window rate limiter and bounded concurrency semaphore (`_PUBLIC_INGEST_SLOTS = 2`) preventing resource exhaustion.
5. **Graph Namespace Isolation:** Every repository and financial dataset receives a dedicated, sanitized graph name (`repo_*`, `fin_*`). Scenario simulations use ephemeral `scen_*` clones that are dropped immediately after evaluation.
6. **Action Payload Locking:** External actions require cryptographic SHA-256 approval. Direct external action execution is disabled in public demo mode.

### Transparent Disclosures & Known Limitations
- **Git History vs. PR Reviews:** Contributor expertise reflects authored commits in Git history. Pull request review metadata requires GitHub API token ingestion; where absent, the system discloses that PR review records are unavailable.
- **Financial Datasets:** The preloaded financial dataset is a synthetic AML benchmark (`aml_transaction_benchmark.csv`). Risk scores are investigative signals for compliance review, not automated legal findings.
- **AI Model Key Independence:** NexusAct does not require a commercial API key to function. When `GEMINI_API_KEY` is not provided, the system seamlessly transitions to its deterministic Cypher template engine, returning factual row evidence without failure.

---

## 11. Hackathon Submission & Author Disclosures

### Track: Agents That Act on Connected Data
NexusAct fulfills the core tenets of the hackathon track:
- **Connected Data as the Grounding Truth:** FalkorDB graph structures serve as the single source of truth for all agent planning, reasoning, and synthesis.
- **Graph Algorithms as Agent Tools:** Shortest paths, PageRank centrality, and cycle detection are packaged as deterministic tools rather than left to LLM guesswork.
- **Counterfactual Action:** The agent safely branches graph reality using `GRAPH.COPY` to preview architectural consequences before recommending changes.
- **Explainability:** Every investigation finding links to concrete graph nodes, physical code files, and millisecond Cypher execution traces.

### AI Coding Assistant Disclosure (Hackathon Rule 11)
In full compliance with Hackathon Rule 11:
- AI coding assistants (including Google Antigravity IDE and Google Gemini) were utilized during development for pair programming, documentation structuring, and test authoring.
- The author designed the GraphAction Fabric (GAF) architecture, implemented the custom AST parsers, authored the Cypher queries and ephemeral clone algorithms, and takes complete responsibility for all code, design decisions, and system behaviors presented in this repository.

---

## 12. License & Open-Source Status

This repository is maintained as an open-source project for the FalkorDB Graph Hacks Hackathon. Specific licensing terms will be formalized in an upcoming release. All dependencies and container images utilized (FalkorDB, FastAPI, React, Vite) are standard open-source technologies under their respective permissive licenses (BSD, MIT, Apache 2.0).
