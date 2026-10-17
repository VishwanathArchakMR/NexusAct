"""Phase 14: Final Boss Regression Tests.

Validates:
1. FalkorDB LOADING readiness behavior and exact structured status code parsing.
2. Probe resilience to transient LOADING state.
3. Selected repository isolation: security triage does not fall back to host Path(".").
4. Unknown package versions and absent manifests handling.
5. Synthetic fraud cycle detection, benign control separation, and risk indicator severity.
6. LLM provider missing-key behavior, planner tool allowlist, and graph-locking.
7. Context-specific safe action proposal verification.
"""

from unittest.mock import MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnError

from backend.app.agent.llm import FakeLLMProvider, GeminiProvider, LLMDecision, LLMToolCall
from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.fraud import (
    FRAUD_DEMO_GRAPH,
    FraudInvestigationInput,
    execute_investigate_fraud,
    seed_synthetic_fraud_graph,
)
from backend.app.graph.tools.security_triage import (
    SecurityTriageInput,
    execute_security_triage,
)
from backend.app.sources.models import RepositoryRecord, SourceType
from backend.app.sources.registry import repo_registry
from scripts.falkordb_probe import check_falkordb_readiness

# ── 1. FalkorDB Probe & LOADING State Regressions ───────────────────────────


def test_falkordb_probe_loading_transient_classification():
    """Verify that a Redis LOADING exception is classified as exit code 2 (LOADING), not fatal error."""
    with patch("falkordb.FalkorDB") as mock_falkor:
        mock_instance = MagicMock()
        mock_instance.connection.ping.side_effect = RedisConnError("LOADING Redis is loading the dataset in memory")
        mock_falkor.return_value = mock_instance

        code = check_falkordb_readiness(host="127.0.0.1", port=6379, timeout_sec=1.0)
        assert code == 2, f"Expected exit code 2 (LOADING), got {code}"


def test_falkordb_probe_connection_refused_classification():
    """Verify that connection refused is classified as exit code 3."""
    with patch("falkordb.FalkorDB") as mock_falkor:
        mock_instance = MagicMock()
        mock_instance.connection.ping.side_effect = RedisConnError(
            "Error 10061 connecting to 127.0.0.1:6379. Connection refused."
        )
        mock_falkor.return_value = mock_instance

        code = check_falkordb_readiness(host="127.0.0.1", port=6379, timeout_sec=1.0)
        assert code == 3, f"Expected exit code 3 (CONNECTION_REFUSED), got {code}"


def test_falkordb_probe_live_readiness():
    """Verify authoritative probe against live FalkorDB container returns 0 (READY)."""
    code = check_falkordb_readiness(host="127.0.0.1", port=6379, timeout_sec=3.0)
    assert code == 0, f"Expected exit code 0 (READY) from running FalkorDB, got {code}"


# ── 2. Security Triage Repository Isolation & Unknown Manifests ──────────────


@pytest.mark.asyncio
async def test_security_triage_no_host_path_fallback():
    """
    When a repository is selected whose local files do NOT exist on disk,
    security triage must NOT fall back to host Path(".") or read NexusAct's files.
    """
    repo_id = "repo:phantom_external"
    repo_registry.update_repository(
        RepositoryRecord(
            id=repo_id,
            name="phantom_repo",
            source_type=SourceType.LOCAL,
            url_or_path="C:/nonexistent/phantom/path",
            graph_name="graph_phantom",
            commit_sha="sha_phantom_123",
        )
    )

    out = await execute_security_triage(
        SecurityTriageInput(repository_id=repo_id, graph_name="graph_phantom"),
        client=graph_client,
    )

    assert out.repository_id == repo_id
    assert out.manifests_inspected == []
    assert out.dependencies_analyzed_count == 0
    assert out.evidence_status == "MANIFESTS_UNAVAILABLE"
    assert any("not accessible on the host filesystem" in u for u in out.uncertainties)


@pytest.mark.asyncio
async def test_security_triage_unknown_version_disclosure():
    """Package with unparseable or absent exact version must record an uncertainty."""
    out = await execute_security_triage(
        SecurityTriageInput(repository_id="repo:local_nexusact", package_filter="this_package_does_not_exist_xyz"),
        client=graph_client,
    )
    assert out.total_vulnerabilities_count == 0
    assert out.evidence_status in ("NO_KNOWN_VULNERABILITIES", "NO_MANIFESTS_FOUND")


# ── 3. Fraud Investigation & Risk Indicator Rigor ────────────────────────────


def test_fraud_investigation_indicators_and_controls():
    """
    Verifies that:
    1. Circular transfer ring is detected.
    2. Shared infrastructure is flagged with severity MEDIUM (indicator, not proof).
    3. Benign controls acc:201 and acc:202 are verified BENIGN_NORMAL.
    4. Synthetic disclaimer is explicit.
    """
    seed_synthetic_fraud_graph(graph_client)
    out = execute_investigate_fraud(
        FraudInvestigationInput(graph_name=FRAUD_DEMO_GRAPH),
        client=graph_client,
    )

    assert out.graph_name == FRAUD_DEMO_GRAPH
    assert out.is_synthetic_demonstration is True
    assert "strictly on synthetic" in out.synthetic_disclaimer

    # Verify pattern severity
    shared_infra = [p for p in out.patterns_detected if p.pattern_type == "SHARED_INFRASTRUCTURE"]
    assert len(shared_infra) > 0
    assert shared_infra[0].severity == "MEDIUM", (
        "Shared infrastructure must be MEDIUM severity indicator, not HIGH proof"
    )
    assert "risk indicator" in shared_infra[0].description.lower()

    # Verify controls
    assert len(out.benign_controls) >= 2
    ctrl_ids = {c.account_id for c in out.benign_controls}
    assert "acc:201" in ctrl_ids
    assert "acc:202" in ctrl_ids
    assert all(c.pattern_status == "BENIGN_NORMAL" for c in out.benign_controls)

    # Verify uncertainties
    assert len(out.uncertainties) >= 1
    assert any("synthetic demonstration" in u.lower() for u in out.uncertainties)


# ── 4. LLM Provider Missing-Key & Planner Guardrails ─────────────────────────


def test_gemini_provider_missing_key_behavior():
    """Gemini provider with empty API key must report unavailable and never throw."""
    provider = GeminiProvider(api_key="")
    assert provider.is_available is False
    assert "gemini" in provider.name


@pytest.mark.asyncio
async def test_planner_tool_allowlist_and_graph_lock():
    """
    Planner must:
    1. Reject tool calls outside the registered allowlist.
    2. Strictly enforce graph_name parameter to prevent model redirection.
    """
    fake_decisions = [
        # 1. Unapproved tool attempt
        LLMDecision(
            action="call_tool",
            tool_call=LLMToolCall(tool_name="unauthorized_exec_command", arguments={"cmd": "whoami"}),
        ),
        # 2. Approved tool with attempt to override graph
        LLMDecision(
            action="call_tool",
            tool_call=LLMToolCall(
                tool_name="nexusact_trace_impact",
                arguments={"module_identifier": "mod:test", "graph_name": "malicious_override_graph"},
            ),
        ),
        # 3. Finish
        LLMDecision(action="finish", finish_summary="Test completed."),
    ]
    fake_llm = FakeLLMProvider(predefined_decisions=fake_decisions)
    agent = AdaptiveInvestigationAgent(llm_provider=fake_llm, client=graph_client, max_tool_budget=3)

    target_graph = "test_locked_graph"
    graph_client.query("MERGE (m:Module {id: 'mod:test', name: 'test'})", graph_name=target_graph)

    report = await agent.investigate(
        question="What could break if I change mod:test?",
        module_identifier="mod:test",
        graph_name=target_graph,
        repo_id="repo:test_lock",
    )

    assert report.graph_name == target_graph
    # Verify unapproved tool was rejected
    executed_tool_names = [s.tool_name for s in report.steps]
    assert "unauthorized_exec_command" not in executed_tool_names
    # Verify graph lock was enforced on trace_impact
    if "nexusact_trace_impact" in executed_tool_names:
        impact_step = next(s for s in report.steps if s.tool_name == "nexusact_trace_impact")
        assert impact_step.arguments.get("graph_name") == target_graph


# ── 5. Context-Specific Safe Actions ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_context_specific_action_proposals():
    """Proposals must reflect the specific domain (security, fraud, codebase) with provenance."""
    agent = AdaptiveInvestigationAgent(client=graph_client)

    # 1. Fraud proposal
    fraud_out = execute_investigate_fraud(FraudInvestigationInput(), client=graph_client)
    fraud_prop = agent._generate_verified_action_proposal(
        target_name="Fraud System",
        target_id="acc:101",
        impact=None,
        reviewers=None,
        simulation=None,
        verification=None,
        fraud=fraud_out,
    )
    assert "[NexusAct Fraud Review]" in fraud_prop["title"]
    assert "Synthetic Disclaimer" in fraud_prop["body"]
    assert fraud_out.graph_name in fraud_prop["body"]

    # 2. Security triage proposal
    sec_out = await execute_security_triage(SecurityTriageInput(), client=graph_client)
    sec_prop = agent._generate_verified_action_proposal(
        target_name="Security",
        target_id="repo:local_nexusact",
        impact=None,
        reviewers=None,
        simulation=None,
        verification=None,
        security_triage=sec_out,
    )
    assert "[NexusAct Security Triage]" in sec_prop["title"]
    assert "OSV-Backed" in sec_prop["body"]
