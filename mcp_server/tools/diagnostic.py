"""Real diagnostic MCP tool for FalkorDB inspection."""

import logging
import sys

from backend.app.core.config import settings
from backend.app.graph.client import graph_client
from backend.app.graph.schema import SCHEMA_VERSION
from mcp_server.registry import tool_registry
from mcp_server.schemas import (
    GraphDiagnosticInput,
    GraphDiagnosticOutput,
    ToolClassification,
)

# MCP diagnostic logs MUST go to sys.stderr so stdout is never polluted for stdio JSON-RPC
logger = logging.getLogger("mcp_server.diagnostic")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s [MCP-DIAG] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

TOOL_NAME = "nexusact_diagnose_graph"
TOOL_VERSION = "1.0.0"


@tool_registry.register(
    name=TOOL_NAME,
    version=TOOL_VERSION,
    description="Inspects FalkorDB graph connectivity, node and edge metrics, schema version, and label inventory.",
    classification=ToolClassification.READ_ONLY,
    input_schema=GraphDiagnosticInput,
    output_schema=GraphDiagnosticOutput,
)
def run_graph_diagnostics(payload: GraphDiagnosticInput) -> GraphDiagnosticOutput:
    """Executes read-only diagnostic check against FalkorDB."""
    target_graph = payload.graph_name or settings.FALKORDB_PRIMARY_GRAPH
    logger.info("Executing diagnostic check on graph: '%s'", target_graph)

    # 1. Check basic socket connectivity
    if not graph_client.ping():
        logger.warning("FalkorDB is unreachable at %s:%d", settings.FALKORDB_HOST, settings.FALKORDB_PORT)
        return GraphDiagnosticOutput(
            tool_version=TOOL_VERSION,
            graph_name=target_graph,
            connected=False,
            status="UNAVAILABLE",
            node_count=0,
            edge_count=0,
            schema_version="unknown",
            labels=[],
            diagnostics_message=f"Cannot reach FalkorDB on {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}",
        )

    # 2. Gather diagnostic metrics
    try:
        diag = graph_client.get_graph_diagnostics(target_graph)
        labels = []
        if payload.include_labels:
            try:
                raw_labels = graph_client.query("CALL db.labels()", graph_name=target_graph)
                labels = [row[0] for row in raw_labels if row]
            except Exception as lexc:
                logger.debug("Could not query labels: %s", lexc)

        return GraphDiagnosticOutput(
            tool_version=TOOL_VERSION,
            graph_name=target_graph,
            connected=True,
            status=diag.get("status", "HEALTHY"),
            node_count=diag.get("node_count", 0),
            edge_count=diag.get("edge_count", 0),
            schema_version=SCHEMA_VERSION,
            labels=labels,
            diagnostics_message=(
                f"Graph '{target_graph}' is active and operational with "
                f"{diag.get('node_count', 0)} nodes and {diag.get('edge_count', 0)} edges."
            ),
        )
    except Exception as exc:
        logger.error("Error during diagnostic inspection: %s", exc)
        return GraphDiagnosticOutput(
            tool_version=TOOL_VERSION,
            graph_name=target_graph,
            connected=True,
            status="DEGRADED",
            node_count=0,
            edge_count=0,
            schema_version=SCHEMA_VERSION,
            labels=[],
            diagnostics_message=f"Graph query degraded: {str(exc)}",
        )
