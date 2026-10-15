"""Deterministic evaluation tests for Adaptive Agent and MCP Tool Chaining.

Covers Section 11 Requirements:
11. Agent tool selections are executed through the MCP interface and recorded.
12. The agent respects its tool-call and query budgets.
14. Missing model credentials do not break database functionality.
"""

import pytest

from backend.app.agent.llm import FakeLLMProvider, LLMDecision, NoneLLMProvider
from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from mcp_server.server import create_mcp_server


@pytest.mark.asyncio
async def test_mcp_server_lists_and_executes_all_tools():
    """Verify that MCP server exposes and executes the 4 core tools over MCP protocol."""
    server = create_mcp_server()
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "nexusact_trace_impact" in tool_names
    assert "nexusact_who_knows" in tool_names
    assert "nexusact_page_rank" in tool_names
    assert "nexusact_simulate_remove_module" in tool_names

    # Test executing PageRank via MCP protocol
    res = await server.call_tool("nexusact_page_rank", {"limit": 3})
    assert getattr(res, "is_error", False) is False
    content = getattr(res, "content", [])
    assert len(content) > 0
    assert "top_modules" in getattr(content[0], "text", "")


@pytest.mark.asyncio
async def test_agent_tool_chaining_and_budget_bounds():
    """Verify that agent chains tools adaptively and strictly respects max_tool_budget."""
    fake_provider = FakeLLMProvider(
        [
            LLMDecision(
                action="call_tool",
                tool_call={
                    "tool_name": "nexusact_trace_impact",
                    "arguments": {"module_identifier": "mod:backend.app.graph.client", "max_depth": 2},
                    "reasoning": "Identify upstream dependencies",
                },
            ),
            LLMDecision(
                action="call_tool",
                tool_call={
                    "tool_name": "nexusact_who_knows",
                    "arguments": {"module_identifier": "mod:backend.app.graph.client", "limit": 3},
                    "reasoning": "Identify module authors",
                },
            ),
            LLMDecision(
                action="finish",
                finish_summary="Adaptive chain satisfied evidence requirement.",
                suggested_action_title="[NexusAct] Test Issue",
                suggested_action_body="Findings body",
            ),
        ]
    )

    agent = AdaptiveInvestigationAgent(llm_provider=fake_provider, max_tool_budget=3)
    report = await agent.investigate(
        question="What is the impact of client.py?",
        module_identifier="backend.app.graph.client",
    )

    assert report.status == "COMPLETED"
    assert report.budget_used == 2
    assert report.budget_remaining == 1
    assert len(report.steps) == 2
    assert report.steps[0].tool_name == "nexusact_trace_impact"
    assert report.steps[1].tool_name == "nexusact_who_knows"
    assert report.summary == "Adaptive chain satisfied evidence requirement."
    assert report.action_proposal is not None
    assert report.action_proposal["title"] == "[NexusAct] Test Issue"


@pytest.mark.asyncio
async def test_agent_persists_investigation_and_steps_in_falkordb():
    """Verify that agent records Investigation and ToolInvocation nodes in FalkorDB."""
    fake_provider = FakeLLMProvider(
        [
            LLMDecision(
                action="call_tool",
                tool_call={
                    "tool_name": "nexusact_trace_impact",
                    "arguments": {"module_identifier": "mod:backend.app.graph.client"},
                    "reasoning": "Check callers",
                },
            ),
            LLMDecision(action="finish", finish_summary="Done."),
        ]
    )

    agent = AdaptiveInvestigationAgent(llm_provider=fake_provider, max_tool_budget=3)
    report = await agent.investigate(
        question="Check telemetry logging",
        module_identifier="backend.app.graph.client",
    )

    inv_id = report.investigation_id
    # Verify in FalkorDB
    inv_nodes = graph_client.query(
        "MATCH (inv:Investigation {id: $id}) RETURN inv.id, inv.status", params={"id": inv_id}
    )
    assert len(inv_nodes) == 1
    assert inv_nodes[0][1] == "COMPLETED"

    # Verify tool invocation nodes
    tool_nodes = graph_client.query(
        "MATCH (inv:Investigation {id: $id})-[:USED_TOOL]->(t:ToolInvocation) RETURN t.tool_name",
        params={"id": inv_id},
    )
    assert len(tool_nodes) == 1
    assert tool_nodes[0][0] == "nexusact_trace_impact"


@pytest.mark.asyncio
async def test_missing_model_credentials_does_not_break_system():
    """Verify that when no LLM is configured, the agent runs honestly via heuristic chain without crashing."""
    none_provider = NoneLLMProvider()
    assert none_provider.is_available is False

    # The agent should detect unavailable provider and use honest deterministic evidence gathering
    agent = AdaptiveInvestigationAgent(llm_provider=none_provider, max_tool_budget=3)
    report = await agent.investigate(
        question="Analyze without model",
        module_identifier="backend.app.graph.client",
    )

    assert report.status == "COMPLETED"
    assert report.budget_used > 0
    assert report.verification is not None
    assert report.verification.status.value in ("VERIFIED", "SUPPORTED")
