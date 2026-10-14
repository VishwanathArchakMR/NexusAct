# NexusAct — Model Context Protocol (MCP) Design

## 1. Overview and Purpose

NexusAct implements an MCP server adhering to the official Model Context Protocol specification (`mcp` v2.3.0 SDK). The MCP server exposes restricted, deterministic, typed tools that AI agent clients (Claude Desktop, Cursor, Antigravity, local agents) can invoke to query repository telemetry and connected graph relationships.

## 2. Safety Design & Restriction Principles

1. **No Arbitrary Cypher Execution:** The model is strictly prohibited from sending raw Cypher queries to the database. All operations are mediated through predefined, parameterized tools with input validation.
2. **Tool Classification:**
   - `READ_ONLY`: Gathers telemetry or traverses paths. Zero mutation side-effects.
   - `MUTATING`: Creates scenario graph copies or applies labels within an isolated copy.
   - `DESTRUCTIVE`: Cleans up temporary scenario graphs. Primary production graphs (`nexusact_main`) are strictly protected from deletion.
3. **Stdio Protocol Cleanliness:** Diagnostic logs are sent exclusively to standard error (`sys.stderr`). Standard output (`sys.stdout`) is reserved strictly for JSON-RPC 2.0 frames.

## 3. Phase 1 Diagnostic Tool Contract

### Tool: `nexusact_diagnose_graph`
- **Classification:** `READ_ONLY`
- **Version:** `1.0.0`
- **Description:** "Inspects FalkorDB graph connectivity, node and edge metrics, schema version, and label inventory."

#### Input Contract (`GraphDiagnosticInput`)
```json
{
  "graph_name": "nexusact_main", // optional, defaults to primary graph
  "include_labels": true          // optional boolean
}
```

#### Output Contract (`GraphDiagnosticOutput`)
```json
{
  "tool_version": "1.0.0",
  "graph_name": "nexusact_main",
  "connected": true,
  "status": "HEALTHY",
  "node_count": 5,
  "edge_count": 6,
  "schema_version": "1.0.0",
  "labels": ["Module", "Person"],
  "diagnostics_message": "Graph 'nexusact_main' is active and operational with 5 nodes and 6 edges."
}
```

## 4. Local Invocation & Protocol Smoke Testing

Run the automated protocol-level smoke test:
```powershell
.\.venv\Scripts\pytest tests/smoke/test_mcp_diagnostic.py -v
```

To configure in an external MCP client (e.g., Claude Desktop or Cursor):
```json
{
  "mcpServers": {
    "nexusact": {
      "command": "C:/NexusAct/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:/NexusAct"
    }
  }
}
```
