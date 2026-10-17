"""Integration and regression test suite for Phase 22 Stage 1 Runtime Recovery.

Validates:
1. Dynamic entity & path target resolution in selected repositories (AletheiaOS vs NexusAct)
2. Accurate source-specific diagnostics telemetry via ?repo_id=
3. Recent graph investigations persistence across graphs with mode, repo_id, and commit_sha
4. Safe LLM configuration fallback and bounded connectivity diagnostic disclosures
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.planner import AdaptiveInvestigationAgent, InvestigationReport
from backend.app.graph.client import graph_client
from backend.app.main import app
from backend.app.sources.registry import repo_registry


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def seed_test_graphs():
    """Ensure minimal module graphs exist in FalkorDB for tests running in CI on empty databases."""
    alethe_graph = "repo_vishwanatharchakmr_alethe"
    try:
        res_alethe = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name=alethe_graph)
        if not res_alethe or res_alethe[0][0] == 0:
            graph_client.query(
                """
                MERGE (m1:Module {id: 'mod:frontend.src.lib.api', name: 'frontend.src.lib.api'})
                MERGE (m2:Module {id: 'mod:backend.app.graph.client', name: 'backend.app.graph.client'})
                MERGE (m1)-[:DEPENDS_ON]->(m2)
                """,
                graph_name=alethe_graph,
            )
    except Exception:
        pass

    try:
        res_nexus = graph_client.query("MATCH (m:Module) RETURN count(m)", graph_name="nexusact_main")
        if not res_nexus or res_nexus[0][0] == 0:
            graph_client.query(
                """
                MERGE (m1:Module {id: 'mod:backend.app.api.router', name: 'backend.app.api.router'})
                MERGE (m2:Module {id: 'mod:backend.app.graph.client', name: 'backend.app.graph.client'})
                MERGE (m1)-[:DEPENDS_ON]->(m2)
                """,
                graph_name="nexusact_main",
            )
    except Exception:
        pass


@pytest.mark.asyncio
async def test_selected_repository_target_resolution_and_path_traversal():
    """Verify that investigating AletheiaOS resolves real modules in AletheiaOS
    and does not hardcode NexusAct internal modules.
    """
    alethe_repo = repo_registry.get_repository("repo:vishwanatharchakmr_aletheiaos")
    assert alethe_repo is not None

    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=3)
    report: InvestigationReport = await agent.investigate(
        question="How does the API route requests to the graph storage engine?",
        repo_id="repo:vishwanatharchakmr_aletheiaos",
        investigation_mode="codebase_walkthrough",
    )

    assert report.repository_id == "repo:vishwanatharchakmr_aletheiaos"
    assert report.graph_name == alethe_repo.graph_name
    # Must NOT have targeted NexusAct internal router in AletheiaOS
    assert "backend.app.api.router" not in report.target_module_id
    # Verification status should not be contradicted due to nonexistent foreign modules
    assert report.verification is not None
    assert report.verification.status.value in ("VERIFIED", "SUPPORTED")


def test_system_status_repo_id_parameter(client):
    """Verify GET /api/v1/system/status reflects the requested repo_id and not unconditionally repo:local_nexusact."""
    # 1. Default request
    res_default = client.get("/api/v1/system/status")
    assert res_default.status_code == 200
    data_def = res_default.json()
    assert data_def["active_repo_id"] == "repo:local_nexusact"

    # 2. Query with AletheiaOS repo_id
    res_alethe = client.get("/api/v1/system/status?repo_id=repo:vishwanatharchakmr_aletheiaos")
    assert res_alethe.status_code == 200
    data_alethe = res_alethe.json()
    assert data_alethe["active_repo_id"] == "repo:vishwanatharchakmr_aletheiaos"
    assert "AletheiaOS" in data_alethe["active_repo_name"]
    assert data_alethe["commit_sha"].startswith("83d1ae15")


def test_recent_investigations_endpoint(client):
    """Verify GET /api/v1/investigation/recent returns real investigations stored across FalkorDB graphs."""
    res = client.get("/api/v1/investigation/recent?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "investigations" in data
    assert isinstance(data["investigations"], list)
    assert data["total"] >= len(data["investigations"])

    if data["investigations"]:
        first = data["investigations"][0]
        assert "investigation_id" in first
        assert "question" in first
        assert "investigation_mode" in first
        assert "repository_id" in first
        assert "graph_name" in first


def test_llm_connectivity_honest_fallback_disclosure(client):
    """Verify test_llm_connectivity truthfully reports NOT_CONFIGURED or PROVIDER_UNAVAILABLE when no key exists."""
    res = client.post("/api/v1/system/llm-test")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("NOT_CONFIGURED", "GEMINI_ACTIVE", "PROVIDER_UNAVAILABLE")
    if data["status"] == "NOT_CONFIGURED":
        assert data["credentials_detected"] is False
        assert "No server-side GEMINI_API_KEY detected" in data["message"]


@pytest.mark.asyncio
async def test_local_nexusact_investigation_workflow():
    """Verify that investigating local NexusAct repository still uses its verified router -> client path."""
    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=3)
    report: InvestigationReport = await agent.investigate(
        question="How does the API route requests to the graph storage engine?",
        repo_id="repo:local_nexusact",
        investigation_mode="codebase_walkthrough",
    )

    assert report.repository_id == "repo:local_nexusact"
    assert report.graph_name == "nexusact_main"
    assert "backend.app.api.router" in report.target_module_id
    assert report.verification is not None
    assert report.verification.status.value in ("VERIFIED", "SUPPORTED")
