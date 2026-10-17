# NexusAct — Final Judge & Evaluator Demonstration Checklist

**Track**: Agents That Act on Connected Data  
**Primary Graph Database**: FalkorDB v4.4.1 (RedisGraph protocol)  
**Target Environments**: Local Development (FastAPI + Vite + FalkorDB) & Production Containers  
**Verified Git Baseline**: `8f932e6` (Stage 1) → Stage 2 CI Green Release  

---

## 1. Quick Start & Service Verification

1. **Verify FalkorDB Connection**:
   - FalkorDB runs as a container on `127.0.0.1:6379`.
   - Verify health check: `redis-cli -h 127.0.0.1 -p 6379 ping` (Returns `PONG`).
   - Check registered graphs: `GRAPH.LIST` in Redis CLI should list `nexusact_main`, `repo_vishwanatharchakmr_alethe`, and `nexusact_fraud_demo`.

2. **Start Backend Server**:
   ```bash
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
   - Check readiness endpoint: `http://127.0.0.1:8000/api/v1/ready` (`status: "READY"`).
   - Check health endpoint: `http://127.0.0.1:8000/api/v1/health` (`status: "OK"`).

3. **Start Frontend Server**:
   ```bash
   cd frontend
   npm run dev
   ```
   - Opens on `http://localhost:5173`.
   - Production bundle validation: `npm run build` succeeds cleanly.

---

## 2. Demonstration Flow Checklist

### Step 1: System Status & Diagnostic Telemetry
- [ ] Open `http://localhost:5173/diagnostics` (or click **Operational Health & Telemetry** in navigation).
- [ ] Observe the **FalkorDB Engine** card reporting `HEALTHY` (`nexusact_main`, node/edge counts).
- [ ] Observe the **Source Selector Dropdown** in the header. Switch between:
  - `NexusAct (Local Workspace)`: commit SHA matches local `HEAD` (`8f932e6`).
  - `VishwanathArchakMR/AletheiaOS`: commit SHA matches remote snapshot `83d1ae15`.
- [ ] Click **Test LLM Connectivity**:
  - Without an API key: Truthfully reports `NOT_CONFIGURED` with message `"No server-side GEMINI_API_KEY detected. Rule-based heuristic fallback is active and healthy."`
  - With a valid `GEMINI_API_KEY` in `.env`: Bounded real check returns `GEMINI_ACTIVE` with latency in milliseconds and secret redaction.

### Step 2: Independent Workspace Tab Exploration
- [ ] Open the **Investigation Workspace** (`http://localhost:5173/`).
- [ ] In the **Target Repository** selector, select `VishwanathArchakMR/AletheiaOS`.
- [ ] **Without pressing Investigate**:
  - Notice that **Graph Explorer** immediately loads the overview subgraph for AletheiaOS.
  - Switch to **Code Inspector**: The project file tree for AletheiaOS is immediately browsable.
  - Switch to **Source Provenance**: Discloses GitHub Public API source adapters and exact commit revision `83d1ae15`.
  - Switch to **Neighborhood & Paths**: Explains topological connection readiness.

### Step 3: Run Multi-Repo Codebase Investigation
- [ ] With `VishwanathArchakMR/AletheiaOS` selected, enter the question:
  `"How does the API route requests to the graph storage engine?"`
- [ ] Click **Investigate**.
- [ ] Observe the investigation lifecycle:
  - Agent queries FalkorDB dynamically for AletheiaOS modules (`mod:frontend.src.lib.api` and `mod:backend.app.graph.client`).
  - Executes `nexusact_shortest_path` tool step via MCP.
  - Returns `COMPLETED` and `VERIFIED` with topological path highlighted on the canvas.
  - Zero fabricated nodes; zero cross-contamination with NexusAct internal modules.
- [ ] Switch to **Agent MCP Trace**: Inspect the step execution trace, execution time, and tool arguments.
- [ ] Switch to **Reviewers & Authors**: Inspect contributor recommendations derived from commit history.

### Step 4: Verify Local Repository Investigation
- [ ] Switch the **Target Repository** back to `NexusAct (Local Workspace)`.
- [ ] Submit the same question:
  `"How does the API route requests to the graph storage engine?"`
- [ ] Click **Investigate**.
- [ ] Verify that NexusAct's internal architecture (`backend.app.api.router -> backend.app.graph.client`) is traversed and verified cleanly in `nexusact_main`.

### Step 5: Recent Graph Investigations Memory
- [ ] Navigate to the **Investigation Center** tab or reload history.
- [ ] Observe the **Recent Graph Investigations** table:
  - Displays the latest investigations in reverse chronological order.
  - Badges accurately show `Codebase Walkthrough`, `Security Triage`, or `Fraud Demo`.
  - Target / Graph column shows the genuine repository and graph (e.g. `repo:vishwanatharchakmr_aletheiaos` vs `repo:local_nexusact`).
  - Click **Refresh** to verify persistence directly from FalkorDB graph memory.

### Step 6: Isolated Financial Fraud Investigation
- [ ] Switch to the **Fraud Investigation** tab (or launch from Investigation Center).
- [ ] Click **Load Synthetic Benchmark Dataset**.
- [ ] Run transaction cycle detection:
  - Traces multi-hop circular fund transfers across accounts in the isolated `nexusact_fraud_demo` graph.
  - Generates risk score and mule account classifications without leaking codebase graph data.

---

## 3. Human Approval & Safety Safeguards
- [ ] Switch to the **Verified Action** tab.
- [ ] Confirm that issue proposals and code remediation actions are in a `PROPOSED` state.
- [ ] Actions strictly require explicit user confirmation before any issue creation or GitHub submission is triggered.
