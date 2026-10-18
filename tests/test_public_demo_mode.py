"""Tests for PUBLIC_DEMO_MODE protection on ingestion, financial uploads, and actions."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_public_demo_mode_blocks_repo_ingest(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post("/api/v1/ingest", json={"repository_path": "."})
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_blocks_repo_register(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/register",
            json={"url_or_path": "https://github.com/example/repo", "source_type": "github"},
        )
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_blocks_local_clone_and_ingest(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/clone-and-ingest",
            json={"url_or_path": "C:\\private\\workspace", "source_type": "local"},
        )
        assert res.status_code == 403
        assert "only permits HTTPS URLs for public GitHub repositories" in res.json()["detail"]


def test_public_demo_mode_allows_valid_public_github_url_preflight(monkeypatch):
    from backend.app.api.endpoints import ingestion as ingestion_api

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        monkeypatch.setattr(ingestion_api, "_check_public_github_repo_size", lambda url: None)
        payload = ingestion_api.OnboardRepoRequest(
            url_or_path="https://github.com/VishwanathArchakMR/NexusAct",
            source_type="github",
        )
        validated = ingestion_api._validate_public_demo_ingestion_request(payload)
        assert validated.owner == "VishwanathArchakMR"
        assert validated.repo == "NexusAct"


def test_public_demo_mode_rejects_non_github_host(monkeypatch):
    from fastapi import HTTPException

    from backend.app.api.endpoints import ingestion as ingestion_api

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        monkeypatch.setattr(ingestion_api, "_check_public_github_repo_size", lambda url: None)
        payload = ingestion_api.OnboardRepoRequest(
            url_or_path="https://example.com/owner/repo",
            source_type="github",
        )
        with pytest.raises(HTTPException) as exc:
            ingestion_api._validate_public_demo_ingestion_request(payload)
        assert exc.value.status_code == 400


def test_public_demo_mode_blocks_financial_preview(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/finance/preview",
            json={"raw_content": "source,dest,amount\nA,B,100", "filename": "test.csv"},
        )
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_blocks_financial_ingest(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/finance/ingest",
            json={
                "raw_content": "source,dest,amount\nA,B,100",
                "filename": "test.csv",
                "dataset_name": "Test Dataset",
            },
        )
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_blocks_financial_delete(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.delete("/api/v1/finance/datasets/fin_test_123")
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_blocks_action_execute(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/action/execute",
            json={"action_id": "act_test", "approved_payload_hash": "dummyhash"},
        )
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


def test_public_demo_mode_allows_eligible_github_clone_and_ingest(client, monkeypatch):
    """Eligible public GitHub URL succeeds and returns real repository metadata and graph report."""
    from pathlib import Path

    from backend.app.api.endpoints import ingestion as ingestion_api
    from backend.app.ingestion.engine import IngestionReport
    from backend.app.sources.models import CollectionStatus, SourceCapability

    mock_cap = SourceCapability(
        source_id="src:github",
        source_type="github",
        repository_identifier="repo:test_repo",
        data_categories=["code_ast", "git_history"],
        status=CollectionStatus.COLLECTED,
    )
    mock_report = IngestionReport(
        repository_id="repo:vishwanatharchakmr_aletheiaos",
        repository_path="/tmp/aletheiaos",
        repository_name="vishwanatharchakmr_aletheiaos",
        graph_name="vishwanatharchakmr_aletheiaos",
        commit_sha="abcd1234ef567890",
        file_count=14,
        module_count=14,
        import_edge_count=45,
        commit_count=1,
        contributor_count=1,
        resolved_imports_count=45,
        unresolved_imports_count=0,
        ingested_at="2026-10-18T00:00:00Z",
        status="COMPLETED",
    )

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        monkeypatch.setattr(ingestion_api, "_check_public_github_repo_size", lambda url: None)
        monkeypatch.setattr(
            ingestion_api.GitHubRepoFetcher,
            "clone_or_update",
            lambda self, url, depth=1, timeout_seconds=90: (Path("."), "abcd1234ef567890"),
        )
        monkeypatch.setattr(
            ingestion_api.GitHubMetadataCollector,
            "collect_metadata",
            lambda self, owner, repo: ({}, mock_cap),
        )
        monkeypatch.setattr(
            ingestion_api.RepositoryIngestionEngine,
            "ingest",
            lambda self, repo_path, graph_name, repo_id, github_metadata=None: mock_report,
        )

        res = client.post(
            "/api/v1/ingest/clone-and-ingest",
            json={
                "url_or_path": "https://github.com/VishwanathArchakMR/AletheiaOS",
                "source_type": "github",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["repository_id"] == "repo:vishwanatharchakmr_aletheiaos"
        assert data["graph_name"] == "vishwanatharchakmr_aletheiaos"
        assert data["commit_sha"] == "abcd1234ef567890"
        assert data["module_count"] == 14
        assert data["import_edge_count"] == 45
        assert "disabled in public demo mode" not in str(data)


def test_public_demo_mode_rejects_oversized_repository():
    """Repositories exceeding size limit trigger HTTP 413."""
    import httpx
    from fastapi import HTTPException

    from backend.app.api.endpoints import ingestion as ingestion_api
    from backend.app.sources.models import PublicGitHubUrl

    url = PublicGitHubUrl.parse_and_validate("https://github.com/bigowner/bigrepo")
    mock_resp = httpx.Response(200, json={"size": 200000}, request=httpx.Request("GET", "https://api.github.com"))

    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(HTTPException) as exc:
            ingestion_api._check_public_github_repo_size(url)
        assert exc.value.status_code == 413
        assert "accepts repositories up to 100 MB" in exc.value.detail


def test_public_demo_mode_rejects_nonexistent_or_private_repository():
    """Nonexistent or private GitHub repositories trigger HTTP 404."""
    import httpx
    from fastapi import HTTPException

    from backend.app.api.endpoints import ingestion as ingestion_api
    from backend.app.sources.models import PublicGitHubUrl

    url = PublicGitHubUrl.parse_and_validate("https://github.com/privateowner/privaterepo")
    mock_resp = httpx.Response(404, request=httpx.Request("GET", "https://api.github.com"))

    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(HTTPException) as exc:
            ingestion_api._check_public_github_repo_size(url)
        assert exc.value.status_code == 404
        assert "not found or is not public" in exc.value.detail


def test_public_demo_mode_rate_limit(client, monkeypatch):
    """Requests exceeding per-IP limit return HTTP 429."""
    import time

    from backend.app.api.endpoints import ingestion as ingestion_api

    test_ip = "198.51.100.99"
    now = time.monotonic()
    ingestion_api._PUBLIC_INGEST_REQUESTS[test_ip] = [now] * ingestion_api._PUBLIC_INGEST_MAX_PER_IP

    try:
        with patch.object(settings, "PUBLIC_DEMO_MODE", True):
            res = client.post(
                "/api/v1/ingest/clone-and-ingest",
                headers={"X-Forwarded-For": test_ip},
                json={"url_or_path": "https://github.com/VishwanathArchakMR/NexusAct"},
            )
            assert res.status_code == 429
            assert "rate limit reached" in res.json()["detail"]
    finally:
        ingestion_api._PUBLIC_INGEST_REQUESTS.pop(test_ip, None)


def test_public_demo_mode_graph_isolation():
    """Onboarded public repositories are assigned isolated graph names distinct from primary graph."""
    from backend.app.sources.registry import repo_registry

    record = repo_registry.register_github_repository("https://github.com/VishwanathArchakMR/AletheiaOS")
    assert record.graph_name != settings.FALKORDB_PRIMARY_GRAPH
    assert "aletheiaos" in record.graph_name.lower() or "vishwanatharchakmr" in record.graph_name.lower()
    # Confirm another repository gets a different graph name
    record2 = repo_registry.register_github_repository("https://github.com/pallets/flask")
    assert record2.graph_name != record.graph_name
    assert record2.graph_name != settings.FALKORDB_PRIMARY_GRAPH
