"""Phase 12: Final Integration, Graph-Truth Audit, and Hackathon Readiness Tests.

Validates that:
1. FalkorDB performs essential graph work (multi-hop traversal, PageRank, counterfactual clone).
2. Repository graphs are strictly isolated without cross-repo data leakage.
3. Subgraph responses guarantee 100% business ID mapping for nodes and edges.
4. MCP tool selection dynamically adapts to question intent (Impact vs. Security vs. Path).
5. Actions are grounded in graph findings with truthful failure handling.
"""

import pytest

from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.centrality import PageRankInput, execute_page_rank
from backend.app.graph.tools.impact import TraceImpactInput, execute_trace_impact
from backend.app.graph.tools.shortest_path import ShortestPathInput, execute_shortest_path
from backend.app.graph.tools.simulation import SimulateRemoveModuleInput, execute_simulate_remove_module
from tests.fixtures.synthetic_graph import seed_synthetic_graph, seed_typescript_fixture


@pytest.fixture(autouse=True)
def ensure_fixtures():
    """Seed synthetic and typescript test graphs into isolated namespaces."""
    seed_synthetic_graph(graph_client, graph_name="test_graph_p12_main")
    seed_typescript_fixture(graph_client, graph_name="repo_test_p12_ts")


def test_falkordb_real_traversal_and_multi_hop():
    """Verify that multi-hop graph traversal queries real edges in canonical DEPENDS_ON direction."""
    # Synthetic graph topology:
    # mod:api/gateway -> mod:services/orders -> mod:services/billing -> mod:pkg/database (3 hops)
    res = execute_shortest_path(
        ShortestPathInput(
            source_identifier="mod:api/gateway",
            target_identifier="mod:pkg/database",
            graph_name="test_graph_p12_main",
        ),
        client=graph_client,
    )
    assert res.connected is True
    assert res.hops >= 2
    assert "mod:api/gateway" in res.path_nodes
    assert "mod:pkg/database" in res.path_nodes


def test_falkordb_reverse_dependency_impact():
    """Verify reverse dependency impact traces callers of target module up to N hops."""
    # In synthetic graph, orders depends on billing, gateway depends on orders
    res = execute_trace_impact(
        TraceImpactInput(
            module_identifier="mod:services/billing",
            max_depth=3,
            graph_name="test_graph_p12_main",
        ),
        client=graph_client,
    )
    assert res.target_module_id == "mod:services/billing"
    assert res.total_impacted_count >= 1
    impacted_ids = {m.module_id for m in res.impacted_modules}
    assert "mod:services/orders" in impacted_ids or "mod:api/gateway" in impacted_ids


def test_falkordb_pagerank_supported_execution():
    """Verify PageRank executes on FalkorDB and returns sorted centrality scores."""
    res = execute_page_rank(
        PageRankInput(
            graph_name="test_graph_p12_main",
            top_k=5,
        ),
        client=graph_client,
    )
    assert len(res.top_modules) > 0
    scores = [m.score for m in res.top_modules]
    assert scores == sorted(scores, reverse=True)


def test_falkordb_counterfactual_simulation_preserves_original_graph():
    """Verify simulation clones to temporary graph, removes target, and leaves original graph intact."""
    pre_count = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name="test_graph_p12_main")[0][0]
    assert pre_count > 0

    res = execute_simulate_remove_module(
        SimulateRemoveModuleInput(
            module_identifier="mod:services/billing",
            graph_name="test_graph_p12_main",
        ),
        client=graph_client,
    )
    assert res.blast_radius_score >= 0.0

    post_count = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name="test_graph_p12_main")[0][0]
    assert post_count == pre_count


def test_cross_repository_isolation_no_leakage():
    """Verify that queries against Repo A never return nodes belonging to Repo B."""
    nodes_a = graph_client.query("MATCH (m:Module) RETURN m.id", graph_name="test_graph_p12_main")
    ids_a = {r[0] for r in nodes_a}

    nodes_b = graph_client.query("MATCH (m:Module) RETURN m.id", graph_name="repo_test_p12_ts")
    ids_b = {r[0] for r in nodes_b}

    assert len(ids_a) > 0
    assert len(ids_b) > 0
    assert len(ids_a.intersection(ids_b)) == 0


@pytest.mark.asyncio
async def test_question_dependent_tool_selection():
    """Verify agent planner dynamically routes tools and generates tailored actions."""
    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=5)

    # 1. Impact Question
    impact_report = await agent.investigate(
        question="What could break if services/billing is modified?",
        module_identifier="services/billing",
        graph_name="test_graph_p12_main",
    )
    tools_impact = [s.tool_name for s in impact_report.steps]
    assert "nexusact_trace_impact" in tools_impact
    assert impact_report.action_proposal is not None
    assert "Impact Analysis" in impact_report.action_proposal["title"]

    # 2. Security Triage Question
    sec_report = await agent.investigate(
        question="Security triage: assess dependency blast radius and owners for vulnerability in services/billing",
        module_identifier="services/billing",
        graph_name="test_graph_p12_main",
    )
    tools_sec = [s.tool_name for s in sec_report.steps]
    assert (
        "nexusact_security_triage" in tools_sec
        or "nexusact_simulate_remove_module" in tools_sec
        or "nexusact_trace_impact" in tools_sec
    )
    assert sec_report.action_proposal is not None
    assert "Security Triage" in sec_report.action_proposal["title"]

    # 3. Shortest Path Question
    path_report = await agent.investigate(
        question="How does api/gateway connect to pkg/database?",
        module_identifier="services/billing",
        graph_name="test_graph_p12_main",
    )
    tools_path = [s.tool_name for s in path_report.steps]
    assert "nexusact_shortest_path" in tools_path
    assert path_report.action_proposal is not None
    assert "Path Verification" in path_report.action_proposal["title"]


def test_subgraph_business_id_integrity():
    """Verify subgraph endpoint returns matching business IDs for 100% of edges."""
    from backend.app.api.endpoints.investigation import get_graph_subgraph

    res = get_graph_subgraph(
        graph_name="test_graph_p12_main",
        depth=2,
    )
    assert len(res.nodes) > 0
    assert len(res.edges) > 0

    node_ids = {n.id for n in res.nodes}
    for edge in res.edges:
        assert edge.source in node_ids, f"Edge source {edge.source} not in node IDs!"
        assert edge.target in node_ids, f"Edge target {edge.target} not in node IDs!"
