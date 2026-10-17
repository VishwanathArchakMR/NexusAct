"""Phase 23 Integration and Regression Tests: Scenario Simulation, Reviewers Intelligence & AI Chat Drawer.

Validates:
1. GET /api/v1/investigation/simulation-candidates returns active modules with in-degree/out-degree.
2. POST /api/v1/investigation/simulate executes isolated graph copy counterfactual simulation
   without mutating base graph, returning truthful explanations for impacting and zero-impact modules.
3. GET /api/v1/investigation/reviewers separates authorship from review flags and provides transparent scoring.
4. POST /api/v1/investigation/chat executes safe, bounded read-only Cypher queries against FalkorDB
   with execution trace, and strictly blocks mutating queries (CREATE, MERGE, DELETE, etc.).
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.graph.client import graph_client
from backend.app.main import app
from backend.app.sources.models import RepositoryRecord, SourceType
from backend.app.sources.registry import repo_registry


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def seed_phase23_graph():
    """Ensure minimal module and commit graph topology exists for testing in CI."""
    test_repo_id = "repo:test_phase23_repo"
    test_graph = "test_phase23_graph"

    if test_repo_id not in repo_registry._repositories:
        repo_registry._repositories[test_repo_id] = RepositoryRecord(
            id=test_repo_id,
            name="test/phase23",
            owner="test",
            repo="phase23",
            source_type=SourceType.LOCAL,
            url_or_path="c:/NexusAct",
            graph_name=test_graph,
            default_branch="master",
            commit_sha="c0ffee1234567890",
            freshness_status="FRESH",
            status="INGESTED",
        )

    try:
        # Seed nodes and edges for simulation & reviewers
        graph_client.query(
            """
            MERGE (m1:Module {
                id: 'mod:test.entry', name: 'test.entry', path: 'test/entry.py',
                in_degree: 0, out_degree: 1, is_entrypoint: true
            })
            MERGE (m2:Module {
                id: 'mod:test.core', name: 'test.core', path: 'test/core.py',
                in_degree: 1, out_degree: 1, is_entrypoint: false
            })
            MERGE (m3:Module {
                id: 'mod:test.leaf', name: 'test.leaf', path: 'test/leaf.py',
                in_degree: 1, out_degree: 0, is_entrypoint: false
            })
            MERGE (m_iso:Module {
                id: 'mod:test.isolated', name: 'test.isolated', path: 'test/isolated.py',
                in_degree: 0, out_degree: 0, is_entrypoint: false
            })

            MERGE (m1)-[:DEPENDS_ON]->(m2)
            MERGE (m2)-[:DEPENDS_ON]->(m3)

            MERGE (p1:Person {id: 'person:alice@example.com', name: 'Alice Smith', email: 'alice@example.com'})
            MERGE (p2:Person {id: 'person:bob@example.com', name: 'Bob Jones', email: 'bob@example.com'})

            MERGE (c1:Commit {id: 'commit:c1', hash: 'c1', message: 'Add core module', committed_at: 1710000000})
            MERGE (c2:Commit {id: 'commit:c2', hash: 'c2', message: 'Update core module', committed_at: 1710500000})
            MERGE (c3:Commit {id: 'commit:c3', hash: 'c3', message: 'Add isolated module', committed_at: 1710600000})

            MERGE (f1:File {id: 'file:test/core.py', path: 'test/core.py'})
            MERGE (f2:File {id: 'file:test/isolated.py', path: 'test/isolated.py'})

            MERGE (m2)-[:CONTAINS]->(f1)
            MERGE (m_iso)-[:CONTAINS]->(f2)

            MERGE (p1)-[:AUTHORED]->(c1)
            MERGE (p1)-[:AUTHORED]->(c2)
            MERGE (p2)-[:AUTHORED]->(c3)

            MERGE (c1)-[:TOUCHES]->(f1)
            MERGE (c2)-[:TOUCHES]->(f1)
            MERGE (c3)-[:TOUCHES]->(f2)
            """,
            graph_name=test_graph,
        )
    except Exception:
        pass


def test_simulation_candidates_endpoint(client):
    """Test GET /api/v1/investigation/simulation-candidates returns active modules with connectivity degrees."""
    resp = client.get(
        "/api/v1/investigation/simulation-candidates",
        params={"repo_id": "repo:test_phase23_repo", "graph_name": "test_phase23_graph"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == "repo:test_phase23_repo"
    assert data["total"] >= 3
    candidate_ids = [c["id"] for c in data["candidates"]]
    assert "mod:test.core" in candidate_ids
    assert "mod:test.entry" in candidate_ids


def test_simulate_counterfactual_preserves_base_graph(client):
    """Test POST /api/v1/investigation/simulate performs counterfactual analysis without mutating original graph."""
    # Count base graph nodes before simulation
    count_before = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name="test_phase23_graph")
    initial_module_count = count_before[0][0] if count_before else 0
    assert initial_module_count >= 3

    resp = client.post(
        "/api/v1/investigation/simulate",
        json={
            "target_module_id": "mod:test.core",
            "repo_id": "repo:test_phase23_repo",
            "graph_name": "test_phase23_graph",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["simulation"] is not None
    assert data["simulation"]["target_module_id"] == "mod:test.core"
    assert data["simulation"]["baseline_paths_count"] >= 1
    assert data["simulation"]["disappeared_paths_count"] >= 1
    assert data["explanation"] is not None
    assert "disrupted" in data["explanation"]["summary"].lower()

    # Verify base graph was NOT mutated (isolated clone was used)
    count_after = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name="test_phase23_graph")
    final_module_count = count_after[0][0] if count_after else 0
    assert final_module_count == initial_module_count


def test_simulate_zero_impact_explanation_truthfulness(client):
    """Test POST /api/v1/investigation/simulate on isolated leaf/module gives honest zero-impact explanation."""
    resp = client.post(
        "/api/v1/investigation/simulate",
        json={
            "target_module_id": "mod:test.isolated",
            "repo_id": "repo:test_phase23_repo",
            "graph_name": "test_phase23_graph",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    sim = data["simulation"]
    assert sim["disappeared_paths_count"] == 0
    explanation = data["explanation"]
    assert explanation is not None
    # Verify honest zero-impact message without confusing "0 of 0" contradictions
    summary_lower = explanation["summary"].lower()
    assert "0 upstream callers" in summary_lower or "zero-impact" in summary_lower


def test_reviewers_endpoint_separates_authorship_and_review(client):
    """Test GET /api/v1/investigation/reviewers returns ranked authors with commit provenance."""
    resp = client.get(
        "/api/v1/investigation/reviewers",
        params={
            "repo_id": "repo:test_phase23_repo",
            "graph_name": "test_phase23_graph",
            "module_id": "mod:test.core",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == "repo:test_phase23_repo"
    assert len(data["candidates"]) >= 1
    top_cand = data["candidates"][0]
    assert "Alice Smith" in top_cand["name"] or "alice@example.com" in top_cand["person_id"]
    assert top_cand["commits_count"] >= 1
    assert top_cand["is_lead"] is True
    # In test fixture without explicit REVIEWED edges, has_explicit_reviews should be False
    assert data["has_explicit_reviews"] is False
    assert "scoring_formula" in data
    # Explanation should explicitly disclose author-based heuristic
    assert "code authorship touch history" in data["explanation"]["what_you_are_looking_at"]


def test_graph_chat_safe_read_query_and_trace(client):
    """Test POST /api/v1/investigation/chat answers queries with safe Cypher execution traces."""
    resp = client.post(
        "/api/v1/investigation/chat",
        json={
            "question": "How many modules exist in test_phase23_graph?",
            "repo_id": "repo:test_phase23_repo",
            "graph_name": "test_phase23_graph",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] is not None
    assert len(data["query_traces"]) >= 1
    trace = data["query_traces"][0]
    assert trace["status"] == "success"
    assert "MATCH" in trace["cypher_query"]
    assert trace["rows_returned"] >= 1
    assert len(data["answer"]) > 0


def test_graph_chat_blocks_mutating_cypher(client):
    """Test POST /api/v1/investigation/chat strictly blocks write/mutation Cypher injections."""
    resp = client.post(
        "/api/v1/investigation/chat",
        json={
            "question": "Run query: CREATE (n:MaliciousNode {name: 'evil'}) RETURN n",
            "repo_id": "repo:test_phase23_repo",
            "graph_name": "test_phase23_graph",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Query must either be sanitized, rejected, or executed only as safe read-only query
    for trace in data["query_traces"]:
        upper_q = trace["cypher_query"].upper()
        assert "CREATE " not in upper_q
        assert "MERGE " not in upper_q
        assert "DELETE " not in upper_q
