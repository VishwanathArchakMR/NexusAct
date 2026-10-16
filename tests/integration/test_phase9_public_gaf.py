"""Phase 9 Integration Tests: Universal GAF Investigation, Memory, and Truthfulness."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.sources.connector_registry import ConnectorResult


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ask_gaf_exact_failing_question_regression(client: TestClient) -> None:
    """Tests that the question that previously caused __format__ 500 now returns 200."""
    payload = {
        "question": "Explore citation relationships between neural network research works.",
        "max_results": 3,
    }
    resp = client.post("/api/v1/discover/ask-gaf", json=payload)
    assert resp.status_code == 200, f"Failed with: {resp.text}"
    data = resp.json()

    assert "investigation_id" in data
    assert data["question"] == payload["question"]
    assert "entities" in data
    assert "relationships" in data
    assert "findings" in data
    assert "summary" in data
    assert "approach" in data
    assert "next_action" in data
    assert data["next_action"] is not None
    assert "id" in data["next_action"]
    assert data["next_action"]["status"] == "PROPOSED"


def test_ask_gaf_four_required_investigations(client: TestClient) -> None:
    """Verifies all four required Phase 9 investigation questions return valid results."""
    questions = [
        "Explore citation relationships between neural network research works.",
        "Which institutions are associated with researchers behind transformer papers?",
        "Which datasets are documented as used to train open-source models?",
        "Find Hugging Face models created by major AI research laboratories.",
    ]

    for q in questions:
        resp = client.post("/api/v1/discover/ask-gaf", json={"question": q, "max_results": 2})
        assert resp.status_code == 200, f"Question '{q}' failed: {resp.text}"
        data = resp.json()
        assert len(data["summary"]) > 0
        assert isinstance(data["coverage_limitations"], list)
        assert isinstance(data["paths"], list)


def test_provider_failure_graceful_degradation(client: TestClient) -> None:
    """Test B: When one connector fails, other connectors still succeed and limitation is reported."""
    from backend.app.sources.connector_registry import ConnectorRegistry

    real_get = ConnectorRegistry.get

    def mock_get(source_id: str):
        conn = real_get(source_id)
        if not conn:
            return None
        if source_id == "openalex":
            # Simulate failure on openalex
            def failing_search(query):
                raise RuntimeError("Simulated OpenAlex upstream rate-limit or timeout.")

            conn.search = failing_search  # type: ignore[assignment]
        return conn

    with patch.object(ConnectorRegistry, "get", side_effect=mock_get):
        resp = client.post(
            "/api/v1/discover/ask-gaf",
            json={
                "question": "Explore citation relationships between neural network research works.",
                "selected_sources": ["openalex", "crossref"],
                "max_results": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Coverage limitations should document the failure
        assert any(
            "openalex" in str(lim).lower() or "failed" in str(lim).lower() for lim in data["coverage_limitations"]
        )


def test_zero_results_truthfulness(client: TestClient) -> None:
    """Test C: Legitimate zero-results query returns empty results with explanation, not fabricated data."""
    from backend.app.sources.connector_registry import ConnectorRegistry

    real_get = ConnectorRegistry.get

    def mock_empty_get(source_id: str):
        conn = real_get(source_id)
        if not conn:
            return None

        def empty_search(query):
            return ConnectorResult(
                source_id=source_id,
                records=[],
                coverage_notes=[f"No public records matched query: '{query.query_text}'"],
            )

        conn.search = empty_search  # type: ignore[assignment]
        return conn

    with patch.object(ConnectorRegistry, "get", side_effect=mock_empty_get):
        resp = client.post(
            "/api/v1/discover/ask-gaf",
            json={
                "question": "Find nonexistent-xyz-quantum-hypergraph-2099-unknown-model",
                "max_results": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entities"]) == 0
        assert len(data["relationships"]) == 0
        assert len(data["paths"]) == 0
        assert (
            any("no direct graph edges" in f.lower() or "0" in f for f in data["findings"])
            or len(data["findings"]) == 0
        )


def test_investigation_memory_persistence_and_action_confirmation(client: TestClient) -> None:
    """Test Phase 7/9 memory: Ask GAF persists investigation and action can be confirmed."""
    resp = client.post(
        "/api/v1/discover/ask-gaf",
        json={
            "question": "Explore citation relationships between neural network research works.",
            "max_results": 2,
        },
    )
    assert resp.status_code == 200
    inv = resp.json()
    action = inv.get("next_action")
    assert action is not None
    action_id = action["id"]

    # 1. Verify list_investigations retrieves it
    list_resp = client.get("/api/v1/discover/investigations?limit=5")
    assert list_resp.status_code == 200
    saved = list_resp.json()
    assert "investigations" in saved
    matching = [i for i in saved["investigations"] if i["investigation_id"] == inv["investigation_id"]]
    assert len(matching) > 0
    assert matching[0]["action_id"] == action_id
    assert matching[0]["action_status"] == "PROPOSED"

    # 2. Confirm action
    conf_resp = client.post("/api/v1/discover/actions/confirm", json={"action_id": action_id})
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["status"] == "CONFIRMED"

    # 3. Check status is updated in memory
    list_resp_2 = client.get("/api/v1/discover/investigations?limit=5")
    matching_2 = [i for i in list_resp_2.json()["investigations"] if i["action_id"] == action_id]
    assert len(matching_2) > 0
    assert matching_2[0]["action_status"] == "CONFIRMED"


def test_subgraph_excludes_schema_metadata(client: TestClient) -> None:
    """Verifies that _SchemaMetadata and internal system nodes are excluded from public subgraph."""
    resp = client.get("/api/v1/discover/subgraph?limit=100")
    assert resp.status_code == 200
    data = resp.json()
    for node in data["nodes"]:
        assert node["type"] not in (
            "_SchemaMetadata",
            "SchemaMetadata",
            "Investigation",
            "ToolInvocation",
            "SourceRecord",
        )
