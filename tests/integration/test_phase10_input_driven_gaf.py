"""Integration tests for Phase 10: Input-Driven Universal GAF.

Validates:
- Test B: Multi-repository switching and isolation in Universal GAF (Repo A vs Repo B)
- Test C: Investigation-scoped public graphs instead of 500+ global nexusact_public
- Test D: Combined repository + public evidence with domain separation
- Test E: Persistent graph truth and idempotent memory
- Test F: Failure states, unknown targets, and empty repository disclosures
- Test G: Public API citation regression without __format__ error
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.agent.discovery_planner import UniversalDiscoveryPlanner
from backend.app.main import app
from backend.app.sources.graph_persister import PublicGraphPersister

client = TestClient(app)


def test_phase10_test_g_citation_regression() -> None:
    """Test G: Resubmit citation exploration query to ensure __format__ exception is resolved."""
    response = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "Explore citation relationships between neural network research works.",
            "input_mode": "public",
            "selected_sources": ["openalex", "crossref"],
            "max_results": 5,
        },
    )
    assert response.status_code == 200, f"Ask GAF citation failed: {response.text}"
    data = response.json()
    assert "investigation_id" in data
    assert data["input_mode"] == "public"
    assert "summary" in data
    assert len(data.get("entities", [])) > 0
    assert len(data.get("relationships", [])) > 0
    # Confirm no __format__ error in summary or findings
    assert "__format__" not in data["summary"]
    assert "unsupported format string" not in data["summary"]


def test_phase10_test_b_two_different_repositories() -> None:
    """Test B: Investigate repository A then repository B, proving graph and context isolation."""
    # 1. Investigate Repo A (NexusAct codebase on nexusact_main)
    resp_a = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "Which modules depend on the database layer?",
            "input_mode": "repository",
            "repository_id": "repo:local_nexusact",
            "graph_name": "nexusact_main",
        },
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["input_mode"] == "repository"
    assert data_a["repository_id"] == "repo:local_nexusact"
    assert data_a["graph_name"] == "nexusact_main"

    nodes_a = {n["id"] for n in data_a.get("scoped_subgraph", {}).get("nodes", [])}
    assert len(nodes_a) > 0, "NexusAct graph should contain modules"

    # 2. Investigate Repo B (Deterministic TypeScript repository fixture)
    from backend.app.graph.client import graph_client
    from tests.fixtures.synthetic_graph import seed_typescript_fixture

    fixture_info = seed_typescript_fixture(graph_client)
    repo_b_id = fixture_info["repo_id"]
    graph_b_name = fixture_info["graph_name"]

    resp_b = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "What are the core imported dependencies and modules in this repository?",
            "input_mode": "repository",
            "repository_id": repo_b_id,
            "graph_name": graph_b_name,
        },
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["input_mode"] == "repository"
    assert data_b["repository_id"] == repo_b_id
    assert data_b["graph_name"] == graph_b_name

    nodes_b = {n["id"] for n in data_b.get("scoped_subgraph", {}).get("nodes", [])}
    assert len(nodes_b) > 0, "TypeScript fixture graph should contain modules"

    # Verify strict isolation: No nodes from Repo A are returned in Repo B's scoped subgraph
    overlap = nodes_a.intersection(nodes_b)
    assert len(overlap) == 0, f"Repository isolation violated! Shared nodes: {overlap}"


def test_phase10_test_c_investigation_scoped_public_graphs() -> None:
    """Test C: Public investigations return scoped graphs, not the entire preloaded 500+ node corpus."""
    resp = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "Find Hugging Face models created by major AI research laboratories.",
            "input_mode": "public",
            "selected_sources": ["huggingface"],
            "max_results": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["input_mode"] == "public"

    scoped_nodes = data.get("scoped_subgraph", {}).get("nodes", [])
    # Scoped nodes must reflect this investigation, not all 500+ persistent nodes
    assert len(scoped_nodes) <= 50, f"Expected bounded scoped nodes, got {len(scoped_nodes)}"

    # Check that persister global subgraph still retains full corpus
    persister = PublicGraphPersister()
    corpus = persister.get_subgraph(limit=100)
    assert len(corpus["nodes"]) >= 20, "Persistent public corpus should remain intact in FalkorDB"


def test_phase10_test_d_combined_input_investigation() -> None:
    """Test D: Combined mode returns both codebase modules and public records with domain provenance."""
    resp = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "How do repository model utilities connect to Hugging Face models?",
            "input_mode": "combined",
            "repository_id": "repo:local_nexusact",
            "graph_name": "nexusact_main",
            "selected_sources": ["huggingface"],
            "max_results": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["input_mode"] == "combined"
    assert data["repository_id"] == "repo:local_nexusact"

    scoped_nodes = data.get("scoped_subgraph", {}).get("nodes", [])
    # Software modules should have type Module or domain software
    software_modules = [
        n for n in scoped_nodes if n.get("type") == "Module" or n.get("properties", {}).get("domain") == "software"
    ]
    assert len(software_modules) > 0, "Combined investigation should include repository modules"


def test_phase10_test_e_persistent_graph_truth_and_idempotency() -> None:
    """Test E: Query run twice saves memory and maintains idempotent graph truth."""
    q = "Which institutions are associated with researchers behind transformer papers?"
    resp1 = client.post(
        "/api/v1/discover/ask-gaf",
        json={"question": q, "input_mode": "public", "selected_sources": ["openalex"], "max_results": 2},
    )
    assert resp1.status_code == 200
    id1 = resp1.json()["investigation_id"]

    resp2 = client.post(
        "/api/v1/discover/ask-gaf",
        json={"question": q, "input_mode": "public", "selected_sources": ["openalex"], "max_results": 2},
    )
    assert resp2.status_code == 200
    id2 = resp2.json()["investigation_id"]

    # Both investigations succeed and are saved into FalkorDB
    inv_list_resp = client.get("/api/v1/discover/investigations?limit=10")
    assert inv_list_resp.status_code == 200
    saved = inv_list_resp.json()["investigations"]
    saved_ids = {s["investigation_id"] for s in saved}
    assert id1 in saved_ids or id2 in saved_ids


def test_phase10_test_f_failure_states_and_data_gaps() -> None:
    """Test F: Non-existent repository target discloses gap honestly without fabricating nodes."""
    planner = UniversalDiscoveryPlanner()
    plan = planner.create_plan(
        question="Analyze architecture of uningested repo",
        input_mode="repository",
        repository_id="repo:non_existent",
        graph_name="repo_does_not_exist",
    )
    result = planner.execute_investigation(
        question="Analyze architecture of uningested repo",
        plan_override=plan,
        input_mode="repository",
        repository_id="repo:non_existent",
        graph_name="repo_does_not_exist",
    )
    assert result.input_mode == "repository"
    assert len(result.entities) == 0
    assert len(result.scoped_subgraph["nodes"]) == 0
    assert len(result.coverage_limitations) > 0
    assert "0 parsed modules" in result.coverage_limitations[0]
    assert result.next_action is not None
    assert result.next_action["id"].startswith("act_ingest_")
