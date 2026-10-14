"""NexusAct restricted domain-specific MCP server implementation."""

import logging
import sys
from typing import Optional

from mcp.server.mcpserver import MCPServer

from backend.app.core.config import settings
from mcp_server.schemas import GraphDiagnosticInput
from mcp_server.tools.diagnostic import TOOL_NAME, run_graph_diagnostics

# Logging must strictly go to stderr so that stdio transport stdout remains clean JSON-RPC
logger = logging.getLogger("nexusact.mcp")
if not logger.handlers:
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(asctime)s [MCP-SERVER] %(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)
    logger.setLevel(getattr(logging, settings.MCP_LOG_LEVEL.upper(), logging.INFO))


def create_mcp_server() -> MCPServer:
    """Builds and initializes the restricted NexusAct MCP server."""
    server = MCPServer(
        name="nexusact-mcp-server",
        version=settings.APP_VERSION,
        description="NexusAct GraphAction Fabric diagnostic and investigation MCP server",
    )

    @server.tool(
        name=TOOL_NAME,
        description=(
            "Inspects FalkorDB graph connectivity, node and edge metrics, "
            "schema version, and label inventory (Read-only)."
        ),
    )
    def nexusact_diagnose_graph(
        graph_name: Optional[str] = None,
        include_labels: bool = True,
    ) -> str:
        """Read-only diagnostic tool returning bounded graph telemetry."""
        payload = GraphDiagnosticInput(
            graph_name=graph_name,
            include_labels=include_labels,
        )
        output = run_graph_diagnostics(payload)
        return output.model_dump_json()

    return server


mcp_app = create_mcp_server()


def main():
    """Runs the MCP server over standard input/output transport."""
    logger.info("Starting NexusAct MCP Server over stdio transport...")
    mcp_app.run()


if __name__ == "__main__":
    main()
