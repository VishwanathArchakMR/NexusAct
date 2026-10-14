"""Protocol-level smoke test for NexusAct MCP Server and diagnostic tool."""

import json

import pytest

from mcp_server.schemas import GraphDiagnosticOutput
from mcp_server.server import create_mcp_server
from mcp_server.tools.diagnostic import TOOL_NAME


@pytest.mark.asyncio
async def test_mcp_server_lists_diagnostic_tool():
    """Verify that the MCP server initializes and advertises the diagnostic tool."""
    server = create_mcp_server()
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert TOOL_NAME in tool_names, f"Expected {TOOL_NAME} to be registered in MCP tools"


@pytest.mark.asyncio
async def test_mcp_diagnostic_tool_call():
    """Verify that calling the diagnostic tool returns valid typed JSON matching the contract."""
    server = create_mcp_server()

    # Call the registered tool
    result = await server.call_tool(TOOL_NAME, {"graph_name": "nexusact_main", "include_labels": True})

    assert result.is_error is False
    assert len(result.content) > 0

    raw_text = result.content[0].text
    parsed = json.loads(raw_text)

    # Validate against our Pydantic output schema
    diagnostic_output = GraphDiagnosticOutput.model_validate(parsed)
    assert diagnostic_output.graph_name == "nexusact_main"
    assert diagnostic_output.status in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
    assert isinstance(diagnostic_output.node_count, int)
    assert isinstance(diagnostic_output.edge_count, int)
    assert len(diagnostic_output.diagnostics_message) > 0
