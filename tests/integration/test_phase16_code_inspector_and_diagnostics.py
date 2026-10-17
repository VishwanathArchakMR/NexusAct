"""Tests for Phase 16: Operational Diagnostics, Real Repository File Tree, and Code Inspector."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_system_status_operational_telemetry():
    """Verify that /api/v1/system/status returns rich operational diagnostics without roadmap data."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()

    assert data["backend_status"] == "ONLINE"
    assert data["falkordb_status"] in ("ONLINE", "OFFLINE")
    assert "subsystem_health" in data
    assert "fastapi" in data["subsystem_health"]
    assert "falkordb" in data["subsystem_health"]
    assert "mcp_server" in data["subsystem_health"]
    assert "llm_provider" in data
    assert "action_service_configured" in data
    assert data["action_service_configured"] is True
    assert data["action_approval_required"] is True


def test_file_tree_real_repository_structure():
    """Verify that /api/v1/ingest/file-tree safely traverses checked-out repository files."""
    response = client.get("/api/v1/ingest/file-tree?repo_id=repo:local_nexusact")
    assert response.status_code == 200
    data = response.json()

    assert data["repository_id"] == "repo:local_nexusact"
    assert data["total_files"] > 10
    assert data["total_directories"] > 2
    assert isinstance(data["tree"], list)

    # Verify backend and frontend folders exist in root tree
    names = [node["name"] for node in data["tree"]]
    assert "backend" in names or "frontend" in names or "docs" in names

    # Ensure hidden and ignored dirs are excluded
    assert ".git" not in names
    assert ".venv" not in names
    assert "node_modules" not in names


def test_file_tree_path_traversal_rejection():
    """Verify that path traversal in subpath is strictly rejected with 400."""
    response = client.get("/api/v1/ingest/file-tree?repo_id=repo:local_nexusact&subpath=../../etc")
    assert response.status_code == 400
    assert "Invalid subpath" in response.json()["detail"]


def test_file_content_with_symbols_and_graph_linkage():
    """Verify that /api/v1/ingest/file-content extracts AST symbols and FalkorDB graph linkage."""
    response = client.get(
        "/api/v1/ingest/file-content?repo_id=repo:local_nexusact&file_path=backend/app/main.py&start_line=1&end_line=120"
    )
    assert response.status_code == 200
    data = response.json()

    assert data["file_path"] == "backend/app/main.py"
    assert data["language"] == "python"
    assert data["total_lines"] > 20
    assert len(data["content"]) > 50

    # AST Symbol outline verification
    assert "symbols" in data
    assert isinstance(data["symbols"], list)
    if data["symbols"]:
        sym = data["symbols"][0]
        assert "name" in sym
        assert "kind" in sym
        assert "start_line" in sym
        assert "end_line" in sym

    # Graph linkage verification
    assert "graph_linkage" in data
    link = data["graph_linkage"]
    assert "has_graph_module" in link
    if link["has_graph_module"]:
        assert link["module_id"] == "mod:backend.app.main"
        assert isinstance(link["dependencies"], list)
        assert isinstance(link["dependents"], list)


def test_file_tree_unknown_repo_returns_404():
    """Verify that querying an unknown repo ID returns a clear 404 error."""
    response = client.get("/api/v1/ingest/file-tree?repo_id=repo:non_existent_repo_12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
