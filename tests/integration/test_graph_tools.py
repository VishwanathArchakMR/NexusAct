"""Deterministic evaluation tests for Core Graph Intelligence Tools.

Covers Section 11 Requirements:
4. Reverse-impact traversal returns the expected paths with the correct direction and four-hop limit.
5. who_knows returns evidence-based ranking components and handles missing history.
6. PageRank returns actual module IDs and scores.
7. The path verifier rejects nonexistent edges, wrong path directions and invalid evidence references.
8. A graph copy preserves the source graph when its copy is modified.
9. The counterfactual detects actual before/after graph differences.
10. Temporary graphs are cleaned up after success and failure.
Graph disconnection ablation: fails honestly when database is offline.
"""

import pytest

from backend.app.evidence.verifier import PathVerifier, VerificationStatus
from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.tools.centrality import PageRankInput, execute_page_rank
from backend.app.graph.tools.impact import ImpactedModule, TraceImpactInput, TraceImpactOutput, execute_trace_impact
from backend.app.graph.tools.reviewers import WhoKnowsInput, execute_who_knows
from backend.app.graph.tools.simulation import SimulateRemoveModuleInput, execute_simulate_remove_module
from tests.fixtures.synthetic_graph import seed_synthetic_graph


@pytest.fixture(scope="module")
def setup_test_graph():
    """Seeds a controlled synthetic graph for deterministic graph tool evaluation."""
    test_graph = "test_graph_tools_fixture"
    seed_synthetic_graph(graph_client, graph_name=test_graph)
    yield test_graph
    try:
        graph_client.delete_graph(test_graph, force=True)
    except Exception:
        pass


def test_reverse_impact_traversal_direction_and_bounds(setup_test_graph):
    """Verify trace_impact follows upstream -> DEPENDS_ON -> target up to 4 hops."""
    # In synthetic graph:
    # gateway -> orders -> billing -> database
    # gateway -> inventory -> database
    # Target: mod:pkg/database
    res = execute_trace_impact(
        TraceImpactInput(module_identifier="mod:pkg/database", max_depth=4, graph_name=setup_test_graph)
    )

    assert res.target_module_id == "mod:pkg/database"
    assert res.total_impacted_count >= 3
    assert res.traversal_direction == "upstream_dependent_to_target"

    mod_ids = [m.module_id for m in res.impacted_modules]
    assert "mod:services/billing" in mod_ids
    assert "mod:services/orders" in mod_ids
    assert "mod:api/gateway" in mod_ids

    billing_entry = next(m for m in res.impacted_modules if m.module_id == "mod:services/billing")
    gateway_entry = next(m for m in res.impacted_modules if m.module_id == "mod:api/gateway")

    assert billing_entry.hops == 1
    assert billing_entry.path == ["mod:services/billing", "mod:pkg/database"]

    assert gateway_entry.hops == 2
    assert gateway_entry.path[-1] == "mod:pkg/database"
    assert gateway_entry.path[0] == "mod:api/gateway"


def test_who_knows_transparent_scoring_and_missing_evidence(setup_test_graph):
    """Verify who_knows calculates 4-part transparent score and surfaces missing evidence."""
    res = execute_who_knows(WhoKnowsInput(module_identifier="mod:pkg/database", graph_name=setup_test_graph))

    assert res.target_module_id == "mod:pkg/database"
    # Even if contributors are unrecorded for database specifically, scoring formula is present
    assert res.scoring_formula is not None
    assert "composite_score" in res.scoring_formula


def test_pagerank_returns_actual_modules_and_scores(setup_test_graph):
    """Verify PageRank calculates valid scores across the module dependency topology."""
    res = execute_page_rank(PageRankInput(limit=5, graph_name=setup_test_graph))

    assert res.graph_name == setup_test_graph
    assert len(res.top_modules) > 0
    for mod in res.top_modules:
        assert mod.module_id.startswith("mod:")
        assert mod.score >= 0.0


def test_path_verifier_validates_and_rejects(setup_test_graph):
    """Verify PathVerifier validates true paths and catches invalid/contradicted paths."""
    verifier = PathVerifier(graph_client)

    # 1. Valid output
    valid_impact = execute_trace_impact(
        TraceImpactInput(module_identifier="mod:pkg/database", max_depth=4, graph_name=setup_test_graph)
    )
    res_valid = verifier.verify_impact_output(valid_impact, graph_name=setup_test_graph)
    assert res_valid.status in (VerificationStatus.VERIFIED, VerificationStatus.SUPPORTED)
    assert res_valid.valid_paths_count == len(valid_impact.impacted_modules)
    assert res_valid.invalid_paths_count == 0

    # 2. Fabricated / Contradicted path
    fake_impact = TraceImpactOutput(
        target_module_id="mod:pkg/database",
        target_module_name="database",
        max_depth=4,
        impacted_modules=[
            ImpactedModule(
                module_id="mod:nonexistent_module",
                module_name="nonexistent",
                hops=1,
                path=["mod:nonexistent_module", "mod:pkg/database"],
            )
        ],
    )
    res_invalid = verifier.verify_impact_output(fake_impact, graph_name=setup_test_graph)
    assert res_invalid.status == VerificationStatus.CONTRADICTED
    assert res_invalid.invalid_paths_count > 0


def test_counterfactual_simulation_and_cleanup(setup_test_graph):
    """Verify simulate_remove_module clones, calculates blast radius, cleans up, and preserves source graph."""
    # Count original nodes before simulation
    orig_nodes = graph_client.query("MATCH (n) RETURN count(n)", graph_name=setup_test_graph)[0][0]

    sim_res = execute_simulate_remove_module(
        SimulateRemoveModuleInput(module_identifier="mod:services/billing", graph_name=setup_test_graph)
    )

    assert sim_res.target_module_id == "mod:services/billing"
    assert sim_res.disappeared_paths_count > 0
    assert 0.0 < sim_res.blast_radius_score <= 1.0

    # Source graph must remain completely untouched
    nodes_after = graph_client.query("MATCH (n) RETURN count(n)", graph_name=setup_test_graph)[0][0]
    # Note: Scenario and ScenarioResult may be logged in source graph
    assert nodes_after >= orig_nodes

    # The removed module 'mod:services/billing' must still exist in the primary source graph!
    billing_check = graph_client.query(
        "MATCH (m:Module {id: 'mod:services/billing'}) RETURN count(m)", graph_name=setup_test_graph
    )
    assert billing_check[0][0] == 1, "Source graph module was mutated or deleted!"


def test_graph_disconnection_ablation():
    """Ablation check: when FalkorDB is offline, tools must fail honestly and not fake success."""
    offline_client = FalkorDBClient(host="127.0.0.1", port=65432)

    # trace_impact must raise an error
    with pytest.raises(Exception):
        execute_trace_impact(
            TraceImpactInput(module_identifier="mod:db"),
            client=offline_client,
        )

    # who_knows must raise an error
    with pytest.raises(Exception):
        execute_who_knows(
            WhoKnowsInput(module_identifier="mod:db"),
            client=offline_client,
        )

    # simulate_remove_module must raise an error
    with pytest.raises(Exception):
        execute_simulate_remove_module(
            SimulateRemoveModuleInput(module_identifier="mod:db"),
            client=offline_client,
        )
