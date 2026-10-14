# NexusAct — Testing Strategy & Compatibility Matrix

## 1. Test Architecture

The testing strategy is organized into four complementary layers:

```
tests/
├── fixtures/
│   └── synthetic_graph.py      # Deterministic graph seeding and teardown
├── smoke/
│   ├── test_falkordb_capabilities.py # 10 isolated database capability tests
│   └── test_mcp_diagnostic.py        # Protocol-level MCP tool tests
backend/tests/
├── unit/
│   └── test_health_api.py      # FastAPI liveness, correlation ID, CORS
└── integration/
    └── test_readiness_api.py   # FastAPI readiness against live & mock DB
frontend/tests/
└── system_status.test.tsx      # React component rendering & status tests
```

## 2. FalkorDB v4.4.1 Compatibility Matrix (Verified at Runtime)

All capabilities were tested against `falkordb/falkordb:v4.4.1` with actual execution:

| Operation | Test / Syntax Verified | Result | Notes |
|---|---|---|---|
| Basic Connection & Ping | `db.connection.ping()` -> `True` | **PASS** | Validated over TCP 6379 socket |
| Cypher Query Execution | `RETURN 42 AS answer` | **PASS** | Standard Cypher result set parsed |
| Idempotent Schema Creation | `CREATE INDEX FOR (m:Module) ON (m.id)` | **PASS** | Repeated calls catch "already exists" cleanly |
| `GRAPH.COPY` Isolation | `GRAPH.COPY test_src test_copy` | **PASS** | Deep copy verified; source unaffected by mutations |
| Detached Node Deletion | `MATCH (m:Module {id: $id}) DETACH DELETE m` | **PASS** | Node and incident edges cleanly removed |
| PageRank Procedure | `CALL algo.pageRank('Module', 'DEPENDS_ON')` | **PASS** | Returns `[Node, float_score]` tuples |
| ShortestPath Traversal | `RETURN shortestPath((a)-[:DEPENDS_ON*]->(b))` | **PASS** | Returns FalkorDB `Path` object in RETURN clause |
| Standalone Betweenness | `CALL algo.betweenness()` | **UNSUPPORTED** | Not registered in FalkorDB v4.4.1 (use Cypher path alternative) |
| Standalone ShortestPath Proc | `CALL algo.shortestPath()` | **UNSUPPORTED** | Not registered as procedure; use native Cypher `shortestPath(...)` |
| Temporary Graph Cleanup | `g.delete()` | **PASS** | Ephemeral scenario graphs cleanly removed |
| Protected Graph Shield | Deleting `nexusact_main` | **PASS** | Shield raises `ValueError` before touching database |

## 3. How to Run Quality & Test Commands

### Run Everything (One Command)
```powershell
# Windows
.\scripts\check.ps1

# Linux / macOS
./scripts/check.sh
```

### Run Python Tests Only
```powershell
.\.venv\Scripts\pytest -v
```

### Run Frontend Tests & Lint Only
```powershell
cd frontend
npm run lint
npm test
npm run build
```
