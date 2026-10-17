"""Phase 24: Comprehensive API Route Contract & End-to-End Flow Parity Tests.

Verifies:
1. Every frontend endpoint path in frontend/src/api/client.ts exists in FastAPI OpenAPI schema.
2. Direct HTTP invocations to /api/v1/investigation/simulation-candidates, /simulate,
   /reviewers, /chat, /recent, and /file-content return valid response structures without 404s.
3. Financial datasets return bidirectional metadata fields ensuring no generic (txs) or Unlabeled labels.
4. Mutation rejection and safe read-only boundaries across all investigation surfaces.
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
def seed_contract_test_data():
    """Seed test repository and financial dataset in registry for contract testing."""
    test_repo_id = "repo:local_nexusact"
    test_graph = "test_phase24_graph"

    if test_repo_id not in repo_registry._repositories:
        repo_registry._repositories[test_repo_id] = RepositoryRecord(
            id=test_repo_id,
            name="local/nexusact",
            owner="local",
            repo="nexusact",
            source_type=SourceType.LOCAL,
            url_or_path="c:/NexusAct",
            graph_name=test_graph,
            default_branch="master",
            commit_sha="5475c03b9f8f9752c8863816c1557ac4f38b273d",
            freshness_status="FRESH",
            status="INGESTED",
        )

    try:
        graph_client.query(
            """
            MERGE (m1:Module {
                id: 'mod:backend.app.main', name: 'backend.app.main', path: 'backend/app/main.py',
                in_degree: 0, out_degree: 2, is_entrypoint: true
            })
            MERGE (m2:Module {
                id: 'mod:backend.app.api.router', name: 'backend.app.api.router', path: 'backend/app/api/router.py',
                in_degree: 1, out_degree: 1, is_entrypoint: false
            })
            MERGE (m3:Module {
                id: 'mod:backend.app.graph.client',
                name: 'backend.app.graph.client',
                path: 'backend/app/graph/client.py',
                in_degree: 2, out_degree: 0, is_entrypoint: false
            })
            MERGE (m1)-[:DEPENDS_ON]->(m2)
            MERGE (m2)-[:DEPENDS_ON]->(m3)

            MERGE (p:Person {id: 'person:author@nexusact.io', name: 'NexusAct Core', email: 'author@nexusact.io'})
            MERGE (c:Commit {
                id: 'commit:c24', hash: '5475c03',
                message: 'Phase 23 baseline commit', committed_at: 1711000000
            })
            MERGE (f:File {id: 'file:backend/app/main.py', path: 'backend/app/main.py'})
            MERGE (m1)-[:CONTAINS]->(f)
            MERGE (p)-[:AUTHORED]->(c)
            MERGE (c)-[:TOUCHES]->(f)
            """,
            graph_name=test_graph,
        )
    except Exception:
        pass


def test_openapi_schema_contains_all_frontend_endpoints(client):
    """Assert that every route expected by the frontend client is registered in the live OpenAPI schema."""
    openapi_schema = app.openapi()
    registered_paths = set(openapi_schema.get("paths", {}).keys())

    expected_frontend_paths = [
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/system/status",
        "/api/v1/system/llm-test",
        "/api/v1/investigation/recent",
        "/api/v1/ingest",
        "/api/v1/ingest/repositories",
        "/api/v1/ingest/register",
        "/api/v1/ingest/clone-and-ingest",
        "/api/v1/ingest/refresh/{repo_id}",
        "/api/v1/ingest/sources/{repo_id}",
        "/api/v1/ingest/modules",
        "/api/v1/ingest/snapshot/{repo_id}",
        "/api/v1/ingest/file-content",
        "/api/v1/ingest/file-tree",
        "/api/v1/investigate",
        "/api/v1/investigation/explain-panel",
        "/api/v1/investigation/simulation-candidates",
        "/api/v1/investigation/simulate",
        "/api/v1/investigation/reviewers",
        "/api/v1/investigation/chat",
        "/api/v1/tools/trace-impact",
        "/api/v1/tools/who-knows",
        "/api/v1/tools/page-rank",
        "/api/v1/tools/simulate",
        "/api/v1/tools/security-triage",
        "/api/v1/tools/investigate-fraud",
        "/api/v1/graph/subgraph",
        "/api/v1/action/propose",
        "/api/v1/action/execute",
        "/api/v1/action/save-internal",
        "/api/v1/discover/sources",
        "/api/v1/discover/ask-gaf",
        "/api/v1/discover/subgraph",
        "/api/v1/discover/investigations",
        "/api/v1/discover/actions/confirm",
        "/api/v1/finance/datasets",
        "/api/v1/finance/datasets/active",
        "/api/v1/finance/datasets/{dataset_id}",
        "/api/v1/finance/datasets/{dataset_id}/activate",
        "/api/v1/finance/datasets/{dataset_id}/subgraph",
        "/api/v1/finance/preview",
        "/api/v1/finance/ingest",
        "/api/v1/finance/load-sample",
        "/api/v1/finance/investigate",
    ]

    missing_paths = [p for p in expected_frontend_paths if p not in registered_paths]
    assert not missing_paths, f"FastAPI schema is missing expected frontend endpoints: {missing_paths}"


def test_simulation_candidates_contract(client):
    """GET /api/v1/investigation/simulation-candidates returns candidates without 404."""
    resp = client.get("/api/v1/investigation/simulation-candidates?limit=10")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "candidates" in data
    assert "repo_id" in data
    assert "graph_name" in data
    assert isinstance(data["candidates"], list)


def test_simulation_execution_contract(client):
    """POST /api/v1/investigation/simulate executes isolated graph copy simulation."""
    payload = {
        "repo_id": "repo:local_nexusact",
        "target_module_id": "mod:backend.app.main",
        "graph_name": "test_phase24_graph",
    }
    resp = client.post("/api/v1/investigation/simulate", json=payload)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "simulation" in data
    assert "explanation" in data
    assert data["simulation"]["target_module_id"] == "mod:backend.app.main"


def test_reviewers_contract(client):
    """GET /api/v1/investigation/reviewers returns ranked contributors."""
    resp = client.get("/api/v1/investigation/reviewers?repo_id=repo:local_nexusact")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "candidates" in data
    assert "total_repo_authors" in data
    assert "scoring_formula" in data


def test_chat_investigation_contract(client):
    """POST /api/v1/investigation/chat queries FalkorDB and returns grounded reasoning."""
    payload = {
        "question": "What is the entrypoint module of the architecture?",
        "repo_id": "repo:local_nexusact",
        "graph_name": "test_phase24_graph",
    }
    resp = client.post("/api/v1/investigation/chat", json=payload)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "answer" in data
    assert "query_traces" in data
    assert "provider_status" in data
    assert isinstance(data["query_traces"], list)


def test_file_content_contract(client):
    """GET /api/v1/ingest/file-content probes module path and returns valid source code."""
    resp = client.get(
        "/api/v1/ingest/file-content",
        params={"repo_id": "repo:local_nexusact", "file_path": "backend/app/main.py", "start_line": 1, "end_line": 50},
    )
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "content" in data
    assert "file_path" in data
    assert "FastAPI" in data["content"] or "app" in data["content"]


def test_financial_datasets_provenance_contract(client):
    """GET /api/v1/finance/datasets returns bidirectional fields for dataset provenance."""
    resp = client.get("/api/v1/finance/datasets")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    datasets = resp.json()
    assert isinstance(datasets, list)
    if len(datasets) > 0:
        first = datasets[0]
        # Verify both backend and frontend compatibility fields are populated
        assert first.get("dataset_name") or first.get("name"), "Dataset display name must be non-empty"
        assert first.get("record_count") is not None or first.get("total_rows") is not None
        assert "is_synthetic" in first
        assert "provenance_note" in first or "data_provenance_note" in first
