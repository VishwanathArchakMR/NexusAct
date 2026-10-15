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

    @server.tool(
        name="nexusact_trace_impact",
        description=(
            "Finds dependent modules that may be affected by changes to a target module "
            "via bounded reverse traversal (up to 4 hops)."
        ),
    )
    def nexusact_trace_impact(
        module_identifier: str,
        max_depth: int = 4,
        limit: int = 50,
        graph_name: Optional[str] = None,
    ) -> str:
        """Bounded reverse dependency traversal tool."""
        from backend.app.graph.tools.impact import TraceImpactInput, execute_trace_impact

        payload = TraceImpactInput(
            module_identifier=module_identifier,
            max_depth=max_depth,
            limit=limit,
            graph_name=graph_name,
        )
        output = execute_trace_impact(payload)
        return output.model_dump_json()

    @server.tool(
        name="nexusact_who_knows",
        description=(
            "Identifies developers with relevant recorded experience and transparent scoring "
            "for a target module and its affected components."
        ),
    )
    def nexusact_who_knows(
        module_identifier: str,
        affected_modules: Optional[list[str]] = None,
        limit: int = 5,
        graph_name: Optional[str] = None,
    ) -> str:
        """Evidence-based reviewer and code owner discovery."""
        from backend.app.graph.tools.reviewers import WhoKnowsInput, execute_who_knows

        payload = WhoKnowsInput(
            module_identifier=module_identifier,
            affected_modules=affected_modules or [],
            limit=limit,
            graph_name=graph_name,
        )
        output = execute_who_knows(payload)
        return output.model_dump_json()

    @server.tool(
        name="nexusact_page_rank",
        description=(
            "Calculates structural centrality across the module dependency graph using FalkorDB native PageRank."
        ),
    )
    def nexusact_page_rank(
        limit: int = 10,
        graph_name: Optional[str] = None,
    ) -> str:
        """Structural centrality analysis using PageRank algorithm."""
        from backend.app.graph.tools.centrality import PageRankInput, execute_page_rank

        payload = PageRankInput(
            limit=limit,
            graph_name=graph_name,
        )
        output = execute_page_rank(payload)
        return output.model_dump_json()

    @server.tool(
        name="nexusact_simulate_remove_module",
        description=(
            "Counterfactual scenario: safely clones the graph, deletes a target module in the copy, "
            "computes the topological blast radius, and cleans up the temporary graph."
        ),
    )
    def nexusact_simulate_remove_module(
        module_identifier: str,
        graph_name: Optional[str] = None,
    ) -> str:
        """Isolated counterfactual module removal simulation."""
        from backend.app.graph.tools.simulation import SimulateRemoveModuleInput, execute_simulate_remove_module

        payload = SimulateRemoveModuleInput(
            module_identifier=module_identifier,
            graph_name=graph_name,
        )
        output = execute_simulate_remove_module(payload)
        return output.model_dump_json()

    return server


mcp_app = create_mcp_server()


def main():
    """Runs the MCP server over standard input/output transport."""
    logger.info("Starting NexusAct MCP Server over stdio transport...")
    mcp_app.run()


if __name__ == "__main__":
    main()
