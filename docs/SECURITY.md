# NexusAct — Security Defaults & Action Boundaries

## 1. Local Security Baseline

NexusAct operates under a "least privilege, fail-safe defaults" architectural posture.

### 1.1 Network & Port Isolation
- **FalkorDB Database (Port 6379):** The Docker container port is explicitly bound to `127.0.0.1:6379` (`ports: - "127.0.0.1:6379:6379"`). It is never exposed on `0.0.0.0` or public network adapters.
- **FastAPI Backend (Port 8000):** Defaults to `127.0.0.1` binding.
- **CORS Policies:** Cross-Origin Resource Sharing is strictly constrained to explicit development origins (`http://localhost:5173`, `http://127.0.0.1:5173`). Wildcard `allow_origins=["*"]` is strictly disallowed.

### 1.2 Database Protection & Immutability
- **Primary Graph Safeguard:** Production graph names (`nexusact_main`, `gaf_main`) are registered in `PROTECTED_GRAPHS` in `backend/app/graph/client.py`. Any attempt to call `delete_graph()` or copy into them via scenario tools raises an immediate `ValueError: Safety violation: Cannot delete protected primary graph`.
- **No Arbitrary Cypher Execution:** LLM agents do not have direct Cypher write access. All graph updates occur through pre-compiled, parameterized application methods.

### 1.3 Secret Management & Version Control
- All credentials, tokens, and local paths are isolated in `.env`.
- `.env` is tracked in `.gitignore` and excluded from Git commits.
- `.env.example` contains only non-sensitive templates and safe local defaults.
- No third-party API keys or external credentials (OpenAI, Anthropic, GitHub) are required for core operations, test execution, or local service startup.

## 2. Future Action Boundaries (Phase 2 & Beyond)

When NexusAct executes actions in future phases (e.g. creating GitHub issues or pull requests):
1. **Independent Read-Back Verification:** The agent must verify the generated diff and supporting graph evidence before proposing the action.
2. **Explicit User Approval:** Destructive or external actions require human approval before dispatch.
3. **Audit Trail:** Every agent invocation, counterfactual branch, and proposed action is stored as an immutable audit node in FalkorDB.
