"""Integration tests for FastAPI readiness and system status endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app

client = TestClient(app)


def test_readiness_when_database_is_online():
    """Verify that /api/v1/ready returns 200 READY when FalkorDB is online."""
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["database"]["connected"] is True
    assert data["database"]["host"] == settings.FALKORDB_HOST
    assert data["database"]["port"] == settings.FALKORDB_PORT
    assert "schema_version" in data


def test_readiness_reports_honestly_when_database_is_offline():
    """Verify that /api/v1/ready returns 503 UNAVAILABLE when FalkorDB is down."""
    with patch("backend.app.api.endpoints.health.graph_client.ping", return_value=False):
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "UNAVAILABLE"
        assert data["database"]["connected"] is False


def test_system_status_endpoint():
    """Verify that /api/v1/system/status provides complete metrics for frontend."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == settings.APP_NAME
    assert data["backend_status"] == "ONLINE"
    assert data["falkordb_status"] in ("ONLINE", "OFFLINE")
    assert isinstance(data["node_count"], int)
    assert isinstance(data["edge_count"], int)
    assert data["mcp_server_configured"] is True
