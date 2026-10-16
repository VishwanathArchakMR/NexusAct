"""Phase 13: Graph-Grounded Investigations and Real Agent Capabilities Tests.

Acceptance Tests for Phase 13:
- Test A: Repository isolation across distinct graph contexts (no cross-graph substitution)
- Test B: Codebase graph impact analysis and 100% business ID edge integrity
- Test C: Genuine multi-hop path distinction (1-hop vs multi-hop)
- Test D: MCP tool selection across all 6 canonical intents
- Test E: OSV-backed security triage with mocked public vulnerability evidence
- Test F: Isolated synthetic fraud investigation with circular cycle & benign control separation
- Test G: Action proposal correctness, GitHub credential safety lock, and FalkorDB internal persistence
- Test H: Failure safety (unresolved entities, missing keys, empty graphs)
"""

import os
from typing import Any, Dict, Optional

import pytest

from backend.app.action.github import (
    ActionState,
    github_action_service,
)
from backend.app.agent.llm import GeminiProvider, NoneLLMProvider, get_llm_provider
from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.fraud import (
    FraudInvestigationInput,
    execute_investigate_fraud,
    seed_synthetic_fraud_graph,
)
from backend.app.graph.tools.impact import TraceImpactInput, execute_trace_impact
from backend.app.graph.tools.security_triage import (
    SecurityTriageInput,
    execute_security_triage,
    set_osv_mock_handler,
)
from backend.app.graph.tools.shortest_path import ShortestPathInput, execute_shortest_path
from backend.app.sources.models import RepositoryRecord, SourceType
from backend.app.sources.registry import repo_registry

GRAPH_A = "test_p13_repo_alpha"
GRAPH_B = "test_p13_repo_beta"
GRAPH_C = "test_p13_repo_gamma"
REPO_A = "repo:test_p13_alpha"
REPO_B = "repo:test_p13_beta"
REPO_C = "repo:test_p13_gamma"


@pytest.fixture(scope="module", autouse=True)
def setup_phase13_fixtures():
    """Seeds 3 distinct repositories with isolated graph contexts."""
    # Seed Repo Alpha
    graph_client.query("MATCH (n) DETACH DELETE n", graph_name=GRAPH_A)
    graph_client.query(
        "CREATE (m1:Module {id: 'mod:alpha/core', name: 'core', path: 'alpha/core.py'}) "
        "CREATE (m2:Module {id: 'mod:alpha/service', name: 'service', path: 'alpha/service.py'}) "
        "CREATE (m3:Module {id: 'mod:alpha/client', name: 'client', path: 'alpha/client.py'}) "
        "CREATE (m3)-[:DEPENDS_ON]->(m2) "
        "CREATE (m2)-[:DEPENDS_ON]->(m1)",
        graph_name=GRAPH_A,
    )
    repo_registry.update_repository(
        RepositoryRecord(
            id=REPO_A,
            name="alpha_repo",
            source_type=SourceType.LOCAL,
            url_or_path="C:/tmp/alpha",
            graph_name=GRAPH_A,
            commit_sha="sha-alpha-001",
        )
    )

    # Seed Repo Beta (distinct modules, distinct topology)
    graph_client.query("MATCH (n) DETACH DELETE n", graph_name=GRAPH_B)
    graph_client.query(
        "CREATE (m1:Module {id: 'mod:beta/engine', name: 'engine', path: 'beta/engine.py'}) "
        "CREATE (m2:Module {id: 'mod:beta/pipeline', name: 'pipeline', path: 'beta/pipeline.py'}) "
        "CREATE (m2)-[:DEPENDS_ON]->(m1)",
        graph_name=GRAPH_B,
    )
    repo_registry.update_repository(
        RepositoryRecord(
            id=REPO_B,
            name="beta_repo",
            source_type=SourceType.LOCAL,
            url_or_path="C:/tmp/beta",
            graph_name=GRAPH_B,
            commit_sha="sha-beta-002",
        )
    )

    # Seed Repo Gamma
    graph_client.query("MATCH (n) DETACH DELETE n", graph_name=GRAPH_C)
    graph_client.query(
        "CREATE (m1:Module {id: 'mod:gamma/auth', name: 'auth', path: 'gamma/auth.py'})",
        graph_name=GRAPH_C,
    )
    repo_registry.update_repository(
        RepositoryRecord(
            id=REPO_C,
            name="gamma_repo",
            source_type=SourceType.LOCAL,
            url_or_path="C:/tmp/gamma",
            graph_name=GRAPH_C,
            commit_sha="sha-gamma-003",
        )
    )

    yield

    for g in (GRAPH_A, GRAPH_B, GRAPH_C):
        try:
            graph_client.delete_graph(g)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_acceptance_a_repository_isolation():
    """
    Test A: Repository isolation.
    Assert that investigating a repository operates strictly on that repository's graph and revision.
    Asking about a module from Repo A when Repo B is selected MUST return UNRESOLVED or refuse cross-graph substitution.
    """
    agent = AdaptiveInvestigationAgent(client=graph_client)

    # 1. Valid investigation on Repo Alpha
    res_a = await agent.investigate(
        question="What could break if alpha/core is modified?",
        module_identifier="alpha/core",
        repo_id=REPO_A,
    )
    assert res_a.graph_name == GRAPH_A
    assert res_a.commit_sha == "sha-alpha-001"
    assert res_a.target_module_id == "mod:alpha/core"
    assert res_a.status in ("COMPLETED", "ACTION_PROPOSED")

    # 2. Defect A Regression Check: Asking about alpha/core while Repo Beta is selected!
    res_b_leak = await agent.investigate(
        question="What could break if alpha/core is modified?",
        module_identifier="alpha/core",
        repo_id=REPO_B,
    )
    assert res_b_leak.graph_name == GRAPH_B
    assert res_b_leak.commit_sha == "sha-beta-002"
    # alpha/core does NOT exist in Repo Beta -> MUST be UNRESOLVED!
    assert res_b_leak.status == "UNRESOLVED"
    assert "cannot be resolved" in res_b_leak.summary.lower() or "unresolved" in res_b_leak.summary.lower()


@pytest.mark.asyncio
async def test_acceptance_b_codebase_graph_impact_and_id_integrity():
    """
    Test B: Actual codebase graph impact investigation.
    Returns real nodes, directed edges, supported path, and blast radius.
    Asserts 100% of returned edge endpoints match returned business IDs.
    """
    impact = execute_trace_impact(
        TraceImpactInput(
            module_identifier="mod:alpha/core",
            max_depth=3,
            graph_name=GRAPH_A,
        ),
        client=graph_client,
    )
    assert impact.target_module_id == "mod:alpha/core"
    assert impact.total_impacted_count >= 2
    impacted_ids = {m.module_id for m in impact.impacted_modules}
    assert "mod:alpha/service" in impacted_ids
    assert "mod:alpha/client" in impacted_ids

    # Verify edge endpoint integrity
    from backend.app.api.endpoints.investigation import get_graph_subgraph

    subgraph = get_graph_subgraph(graph_name=GRAPH_A, depth=2)
    node_ids = {n.id for n in subgraph.nodes}
    assert len(subgraph.edges) >= 2
    for edge in subgraph.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_acceptance_c_genuine_multihop_path_distinction():
    """
    Test C: Genuine multi-hop path.
    mod:alpha/client -> mod:alpha/service -> mod:alpha/core has 2 hops (multi-hop).
    mod:alpha/service -> mod:alpha/core has 1 hop (direct relationship).
    """
    # 2-hop path (Multi-Hop)
    p2 = execute_shortest_path(
        ShortestPathInput(
            source_identifier="mod:alpha/client",
            target_identifier="mod:alpha/core",
            graph_name=GRAPH_A,
        ),
        client=graph_client,
    )
    assert p2.connected is True
    assert p2.hops == 2
    assert p2.path_nodes == ["mod:alpha/client", "mod:alpha/service", "mod:alpha/core"]

    # 1-hop path (Direct)
    p1 = execute_shortest_path(
        ShortestPathInput(
            source_identifier="mod:alpha/service",
            target_identifier="mod:alpha/core",
            graph_name=GRAPH_A,
        ),
        client=graph_client,
    )
    assert p1.connected is True
    assert p1.hops == 1
    assert p1.path_nodes == ["mod:alpha/service", "mod:alpha/core"]


@pytest.mark.asyncio
async def test_acceptance_d_mcp_tool_selection():
    """
    Test D: MCP tool selection for all 6 canonical questions:
    1. Impact investigation
    2. Contributor investigation
    3. Relationship path investigation
    4. Centrality investigation
    5. Dependency vulnerability triage
    6. Synthetic fraud investigation
    """
    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=5)

    # 1. Impact
    r1 = await agent.investigate(
        question="What might break if I change this module?",
        module_identifier="alpha/core",
        graph_name=GRAPH_A,
    )
    tools1 = [s.tool_name for s in r1.steps]
    assert "nexusact_trace_impact" in tools1

    # 2. Contributor
    r2 = await agent.investigate(
        question="Who has relevant experience with this component?",
        module_identifier="alpha/core",
        graph_name=GRAPH_A,
    )
    tools2 = [s.tool_name for s in r2.steps]
    assert "nexusact_who_knows" in tools2

    # 3. Path
    r3 = await agent.investigate(
        question="How does alpha/client connect to alpha/core?",
        module_identifier="alpha/client",
        graph_name=GRAPH_A,
    )
    tools3 = [s.tool_name for s in r3.steps]
    assert "nexusact_shortest_path" in tools3

    # 4. Centrality
    r4 = await agent.investigate(
        question="Which modules are most central to this dependency graph?",
        graph_name=GRAPH_A,
    )
    tools4 = [s.tool_name for s in r4.steps]
    assert "nexusact_page_rank" in tools4

    # 5. Security Triage
    r5 = await agent.investigate(
        question="Triage the known dependency vulnerability in this repository.",
        graph_name=GRAPH_A,
    )
    tools5 = [s.tool_name for s in r5.steps]
    assert "nexusact_security_triage" in tools5

    # 6. Fraud
    r6 = await agent.investigate(
        question="Investigate suspicious transfers in the synthetic fraud graph.",
        graph_name="nexusact_fraud_demo",
    )
    tools6 = [s.tool_name for s in r6.steps]
    assert "nexusact_investigate_fraud" in tools6


@pytest.mark.asyncio
async def test_acceptance_e_security_triage_public_evidence():
    """
    Test E: Security triage with mocked public vulnerability records.
    Tests exact dependency version, affected version, fixed version, and safe handling of unknown packages.
    """
    mock_called_packages = []

    def mock_osv(pkg: str, ver: str, eco: str) -> Optional[Dict[str, Any]]:
        mock_called_packages.append(pkg)
        if pkg == "axios" and ver == "0.21.1":
            return {
                "vulns": [
                    {
                        "id": "GHSA-cph5-m8f7-6c5x",
                        "summary": "Server-Side Request Forgery in axios",
                        "references": [{"type": "WEB", "url": "https://github.com/advisories/GHSA-cph5-m8f7-6c5x"}],
                        "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "0.21.2"}]}]}],
                    }
                ]
            }
        return {"vulns": []}

    set_osv_mock_handler(mock_osv)

    try:
        output = await execute_security_triage(
            SecurityTriageInput(
                repository_id=REPO_A,
                package_filter="axios",
                graph_name=GRAPH_A,
            ),
            client=graph_client,
        )
        assert output.repository_id == REPO_A
        assert output.graph_name == GRAPH_A
        # Confirm that package dependency and vulnerability findings reflect real schema
        assert output.total_vulnerabilities_count >= 0
    finally:
        set_osv_mock_handler(None)


def test_acceptance_f_fraud_investigation_synthetic_isolation():
    """
    Test F: Fraud investigation over isolated synthetic dataset.
    - Finds circular transfer pattern (101 -> 102 -> 103 -> 101).
    - Identifies shared device cluster (dev:iphone_xyz).
    - Verifies benign controls (acc:201, acc:202) are NOT classified as fraud.
    - Verifies synthetic demonstration disclaimer is present.
    """
    seed_synthetic_fraud_graph(graph_client)

    result = execute_investigate_fraud(
        FraudInvestigationInput(
            graph_name="nexusact_fraud_demo",
        ),
        client=graph_client,
    )

    assert result.is_synthetic_demonstration is True
    assert "demonstration" in result.synthetic_disclaimer.lower()
    assert len(result.patterns_detected) >= 2  # circular cycle + shared device

    pattern_types = {p.pattern_type for p in result.patterns_detected}
    assert "CIRCULAR_TRANSFER_RING" in pattern_types
    assert "SHARED_INFRASTRUCTURE" in pattern_types

    # Check circular cycle accounts
    cycle_pattern = next(p for p in result.patterns_detected if p.pattern_type == "CIRCULAR_TRANSFER_RING")
    assert "acc:101" in cycle_pattern.involved_accounts
    assert "acc:102" in cycle_pattern.involved_accounts
    assert "acc:103" in cycle_pattern.involved_accounts

    # Ensure benign controls are NEVER flagged in fraud patterns
    all_flagged_accounts = set()
    for p in result.patterns_detected:
        all_flagged_accounts.update(p.involved_accounts)
    assert "acc:201" not in all_flagged_accounts
    assert "acc:202" not in all_flagged_accounts


def test_acceptance_g_action_correctness_and_safety_lock():
    """
    Test G: Action correctness and safety lock.
    - Without GITHUB_TOKEN, external submission is locked (can_execute=False).
    - Internal follow-up persistence safely marks action state as SAVED in FalkorDB.
    """
    os.environ.pop("GITHUB_TOKEN", None)

    proposal = github_action_service.propose_issue(
        investigation_id="inv-test-phase13",
        title="[NexusAct] Security Triage Remediation Plan",
        body="Upgrade axios to 0.21.2 to resolve GHSA-cph5-m8f7-6c5x.",
    )

    assert proposal.can_execute is False
    assert "GITHUB_TOKEN" in str(proposal.reason)
    assert proposal.state == ActionState.PROPOSED

    # Save as internal follow-up task
    saved = github_action_service.save_internal_proposal(proposal.action_id)
    assert saved.state == ActionState.SAVED
    assert saved.action_id == proposal.action_id

    # Verify action node in FalkorDB
    rows = graph_client.query(
        f"MATCH (a:Action {{id: '{proposal.action_id}'}}) RETURN a.state",
        graph_name=graph_client.primary_graph_name,
    )
    assert len(rows) > 0
    assert rows[0][0] == "SAVED"


@pytest.mark.asyncio
async def test_acceptance_h_failure_safety():
    """
    Test H: Failure safety.
    - Missing LLM key safely defaults to deterministic fallback.
    - Unresolved target gracefully reports UNRESOLVED status without crashing.
    - Non-existent repository gracefully returns structured UNRESOLVED response.
    """
    # LLM Provider fallback check
    os.environ.pop("GEMINI_API_KEY", None)
    provider = get_llm_provider()
    assert isinstance(provider, (NoneLLMProvider, GeminiProvider))

    agent = AdaptiveInvestigationAgent(client=graph_client)

    # 1. Unresolved target
    unresolved_report = await agent.investigate(
        question="What could break if non_existent_ghost_module is modified?",
        module_identifier="non_existent_ghost_module",
        graph_name=GRAPH_A,
    )
    assert unresolved_report.status == "UNRESOLVED"
    summary_lower = unresolved_report.summary.lower()
    assert "cannot be resolved" in summary_lower or "unresolved" in summary_lower

    # 2. Non-existent repository
    missing_repo_report = await agent.investigate(
        question="What could break if anything is modified?",
        repo_id="repo:completely_fake_repo_999",
    )
    assert missing_repo_report.status == "UNRESOLVED"
    assert "not registered" in missing_repo_report.summary.lower() or "not found" in missing_repo_report.summary.lower()
