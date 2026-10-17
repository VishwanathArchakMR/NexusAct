"""Phase 19 Integration & Regression Tests: Real Graph-Grounded Investigation Engine."""

import pytest

from backend.app.agent.llm import FakeLLMProvider, LLMDecision, NoneLLMProvider
from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.fraud import (
    FraudInvestigationInput,
    execute_investigate_fraud,
    seed_synthetic_fraud_graph,
)


@pytest.mark.asyncio
async def test_codebase_walkthrough_flow_selection():
    """Verify that a path/flow inquiry selects shortest_path rather than blind removal simulation."""
    agent = AdaptiveInvestigationAgent(llm_provider=NoneLLMProvider(), client=graph_client)
    report = await agent.investigate(
        question="How does an API request reach the graph storage layer?",
        investigation_mode="codebase_walkthrough",
    )

    executed_tools = [s.tool_name for s in report.steps]
    assert len(executed_tools) > 0
    # Must use path or neighborhood exploration
    assert "nexusact_shortest_path" in executed_tools or "nexusact_graph_neighborhood" in executed_tools
    # Must NOT blindly execute removal simulation for a flow question
    assert "nexusact_simulate_remove_module" not in executed_tools
    assert report.is_heuristic_fallback is True
    assert report.status == "COMPLETED"


@pytest.mark.asyncio
async def test_codebase_walkthrough_impact_selection():
    """Verify that a change-impact inquiry selects trace_impact and counterfactual simulation."""
    agent = AdaptiveInvestigationAgent(llm_provider=NoneLLMProvider(), client=graph_client)
    report = await agent.investigate(
        question="What might be affected if I modify or remove backend.app.agent.planner?",
        module_identifier="backend.app.agent.planner",
        investigation_mode="codebase_walkthrough",
    )

    executed_tools = [s.tool_name for s in report.steps]
    assert len(executed_tools) > 0
    # Must use trace_impact to discover upstream blast radius
    assert "nexusact_trace_impact" in executed_tools
    assert report.impact_result is not None


@pytest.mark.asyncio
async def test_security_triage_workflow_selection():
    """Verify that security triage workflow selects dependency advisory triage and reachability."""
    agent = AdaptiveInvestigationAgent(llm_provider=NoneLLMProvider(), client=graph_client)
    report = await agent.investigate(
        question="Run OSV security triage across repository dependencies",
        investigation_mode="security_triage",
    )

    executed_tools = [s.tool_name for s in report.steps]
    assert "nexusact_security_triage" in executed_tools
    # Security triage must not run software module removal simulation by default
    assert "nexusact_simulate_remove_module" not in executed_tools
    assert report.security_triage_result is not None
    assert report.status == "COMPLETED"


@pytest.mark.asyncio
async def test_fraud_investigation_workflow_isolation():
    """Verify that fraud demo queries operate strictly on fraud tools and isolated demo graph."""
    agent = AdaptiveInvestigationAgent(llm_provider=NoneLLMProvider(), client=graph_client)
    report = await agent.investigate(
        question="Investigate suspicious circular transfer patterns and shared devices",
        investigation_mode="fraud_demo",
    )

    executed_tools = [s.tool_name for s in report.steps]
    assert "nexusact_investigate_fraud" in executed_tools
    # Must never execute software module tools in fraud workflow
    assert "nexusact_simulate_remove_module" not in executed_tools
    assert "nexusact_trace_impact" not in executed_tools
    assert "nexusact_who_knows" not in executed_tools
    assert report.fraud_result is not None
    assert report.fraud_result.is_synthetic_demonstration is True
    assert report.fraud_result.graph_name == "nexusact_fraud_demo"


def test_fraud_cycle_and_shared_device_in_falkordb():
    """Verify cycle detection, shared device detection, and benign controls against live FalkorDB."""
    # Ensure seeded
    seed_synthetic_fraud_graph(graph_client)

    result = execute_investigate_fraud(
        FraudInvestigationInput(question="Find transfer rings and shared hardware"),
        client=graph_client,
    )

    assert result.graph_name == "nexusact_fraud_demo"
    assert len(result.patterns_detected) >= 2

    # Check Circular Ring Pattern
    cycle_pat = next(
        (p for p in result.patterns_detected if p.pattern_type == "CIRCULAR_TRANSFER_RING"),
        None,
    )
    assert cycle_pat is not None
    assert set(cycle_pat.involved_accounts) == {"acc:101", "acc:102", "acc:103"}
    assert cycle_pat.total_volume_usd > 25000.0
    assert len(cycle_pat.transaction_evidence) == 3
    assert cycle_pat.risk_score >= 0.85

    # Check Shared Device Pattern
    dev_pat = next(
        (p for p in result.patterns_detected if p.pattern_type == "SHARED_INFRASTRUCTURE"),
        None,
    )
    assert dev_pat is not None
    assert "dev:iphone_xyz" in dev_pat.multi_hop_path

    # Check Benign Controls
    assert len(result.benign_controls) == 2
    ctrl_ids = {c.account_id for c in result.benign_controls}
    assert ctrl_ids == {"acc:201", "acc:202"}
    for c in result.benign_controls:
        assert c.status == "BENIGN_NORMAL"
        assert "0 circular cycles detected" in (c.status_reason or c.reason)

    # Check Transparent Risk Factors
    assert len(result.risk_factors) >= 2
    assert result.risk_score >= 0.80


@pytest.mark.asyncio
async def test_planner_loop_detection_terminates_gracefully():
    """Verify planner loop detection stops identical repeated tool calls."""
    # Fake provider that attempts to call the exact same tool with identical args twice
    fake_provider = FakeLLMProvider()
    fake_provider.add_decision(
        LLMDecision(
            action="call_tool",
            tool_call={  # type: ignore[arg-type]
                "tool_name": "nexusact_graph_neighborhood",
                "arguments": {"module_identifier": "backend.app.main", "limit": 20},
                "reasoning": "Explore neighborhood call 1",
            },
        )
    )
    fake_provider.add_decision(
        LLMDecision(
            action="call_tool",
            tool_call={  # type: ignore[arg-type]
                "tool_name": "nexusact_graph_neighborhood",
                "arguments": {"module_identifier": "backend.app.main", "limit": 20},
                "reasoning": "Explore neighborhood repeat call 2",
            },
        )
    )

    agent = AdaptiveInvestigationAgent(llm_provider=fake_provider, client=graph_client)
    report = await agent.investigate(
        question="Inspect backend.app.main",
        module_identifier="backend.app.main",
        investigation_mode="codebase_walkthrough",
    )

    # Must only execute 1 step because second duplicate call triggers loop detection break
    assert len(report.steps) == 1
    assert report.steps[0].tool_name == "nexusact_graph_neighborhood"
    assert report.status == "COMPLETED"
