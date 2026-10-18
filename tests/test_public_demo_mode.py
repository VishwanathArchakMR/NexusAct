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


def test_public_demo_mode_allows_valid_zip_upload(client):
    """Uploaded valid repository ZIP is extracted and ingested into an isolated graph."""
    import io
    import zipfile

    # Build an in-memory zip archive with a valid python module
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("myrepo/core.py", "import os\ndef hello(): return 'world'\n")
        zf.writestr("myrepo/utils.py", "from myrepo.core import hello\n")
    zip_bytes = buf.getvalue()

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/upload-zip",
            files={"file": ("myrepo.zip", zip_bytes, "application/zip")},
            data={"display_name": "Test Uploaded Repo"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["repository_id"].startswith("repo:archive_")
        assert data["graph_name"].startswith("repo_archive_")
        assert data["graph_name"] != settings.FALKORDB_PRIMARY_GRAPH
        assert data["module_count"] >= 1
        assert "disabled in public demo mode" not in str(data)


def test_public_demo_mode_rejects_empty_zip(client):
    """Uploading an empty ZIP archive triggers HTTP 400."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as _:
        pass
    empty_zip = buf.getvalue()

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/upload-zip",
            files={"file": ("empty.zip", empty_zip, "application/zip")},
        )
        assert res.status_code == 400
        assert "empty" in res.json()["detail"].lower()


def test_public_demo_mode_rejects_non_zip_file(client):
    """Uploading non-.zip files triggers HTTP 400."""
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/upload-zip",
            files={"file": ("malicious.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")},
        )
        assert res.status_code == 400
        assert "Only .zip archive format is supported" in res.json()["detail"]


def test_public_demo_mode_rejects_zip_slip_path_traversal(client):
    """ZIP archives containing directory traversal entries are rejected with HTTP 400."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../etc/cron.d/evil", "evil payload")
    evil_zip = buf.getvalue()

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/upload-zip",
            files={"file": ("traversal.zip", evil_zip, "application/zip")},
        )
        assert res.status_code == 400
        assert "traversal" in res.json()["detail"].lower() or "invalid entry path" in res.json()["detail"].lower()


def test_multiprocess_registry_reload_consistency(tmp_path):
    """Worker 2 with stale in-memory cache dynamically reloads disk registry on get_repository and list_repositories."""
    from backend.app.sources.registry import RepositoryRegistry

    reg_file = tmp_path / "shared_repositories.json"

    # Worker 1 initializes and has the local default repo
    worker1 = RepositoryRegistry(cache_file=reg_file)

    # Worker 2 initializes at the same time
    worker2 = RepositoryRegistry(cache_file=reg_file)

    # Worker 1 registers a new GitHub repository
    rec1 = worker1.register_github_repository("https://github.com/VishwanathArchakMR/AletheiaOS")
    assert rec1.id == "repo:vishwanatharchakmr_aletheiaos"

    # Worker 2's in-memory dictionary does not have it initially without reload
    assert "repo:vishwanatharchakmr_aletheiaos" not in worker2._repositories

    # When Worker 2 calls get_repository, it dynamically reloads from disk
    resolved = worker2.get_repository("repo:vishwanatharchakmr_aletheiaos")
    assert resolved is not None
    assert resolved.id == "repo:vishwanatharchakmr_aletheiaos"
    assert resolved.graph_name == rec1.graph_name

    # When Worker 2 calls list_repositories, it contains the new repo
    all_repos = worker2.list_repositories()
    assert any(r.id == "repo:vishwanatharchakmr_aletheiaos" for r in all_repos)


def test_registry_save_failure_raises_error(tmp_path, monkeypatch):
    """Failed registry write raises RuntimeError and does not return false success."""
    from backend.app.sources.registry import RepositoryRegistry

    reg_file = tmp_path / "repositories.json"
    registry = RepositoryRegistry(cache_file=reg_file)

    # Simulate an OS error during write (e.g. disk full or permission error)
    def broken_replace(self, target):
        raise PermissionError("Access denied")

    monkeypatch.setattr("pathlib.Path.replace", broken_replace)

    with pytest.raises(RuntimeError) as exc_info:
        registry.register_github_repository("https://github.com/VishwanathArchakMR/AletheiaOS")
    assert "Failed to persist repository registry" in str(exc_info.value)


def test_full_github_ingestion_lifecycle_consistency(client, monkeypatch, tmp_path):
    """Tests the full lifecycle: ingest -> list -> snapshot -> file-tree -> file-content -> investigation."""

    from backend.app.api.endpoints import ingestion as ingestion_api
    from backend.app.ingestion.engine import IngestionReport
    from backend.app.sources.models import CollectionStatus, SourceCapability

    # Create a dummy checked-out directory with real python files
    fake_checkout = tmp_path / "fake_aletheiaos"
    fake_checkout.mkdir()
    (fake_checkout / "app.py").write_text("import os\ndef start(): return True\n", encoding="utf-8")

    test_repo_id = "repo:vishwanatharchakmr_aletheiaos"
    test_graph = "repo_vishwanatharchakmr_alethe"

    mock_cap = SourceCapability(
        source_id="src:github",
        source_type="github",
        repository_identifier=test_repo_id,
        data_categories=["code_ast", "git_history"],
        status=CollectionStatus.COLLECTED,
    )
    mock_report = IngestionReport(
        repository_id=test_repo_id,
        repository_path=str(fake_checkout),
        repository_name="test_aletheiaos",
        graph_name=test_graph,
        commit_sha="c0ffee123456",
        file_count=1,
        module_count=1,
        import_edge_count=0,
        commit_count=1,
        contributor_count=1,
        resolved_imports_count=0,
        unresolved_imports_count=0,
        ingested_at="2026-10-18T00:00:00Z",
        status="COMPLETED",
    )

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        monkeypatch.setattr(ingestion_api, "_check_public_github_repo_size", lambda url: None)
        monkeypatch.setattr(
            ingestion_api.GitHubRepoFetcher,
            "clone_or_update",
            lambda self, url, depth=1, timeout_seconds=90: (fake_checkout, "c0ffee123456"),
        )
        monkeypatch.setattr(
            ingestion_api.GitHubRepoFetcher,
            "get_repo_cache_dir",
            lambda self, owner, repo: fake_checkout,
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

        # 1. Ingest
        res_ingest = client.post(
            "/api/v1/ingest/clone-and-ingest",
            json={
                "url_or_path": "https://github.com/VishwanathArchakMR/AletheiaOS",
                "source_type": "github",
            },
        )
        assert res_ingest.status_code == 200
        ingest_data = res_ingest.json()
        assert ingest_data["repository_id"] == "repo:vishwanatharchakmr_aletheiaos"
        actual_repo_id = ingest_data["repository_id"]

        # 2. List repositories -> verify present and INGESTED
        res_list = client.get("/api/v1/ingest/repositories")
        assert res_list.status_code == 200
        repos = res_list.json()
        match = next((r for r in repos if r["id"] == actual_repo_id), None)
        assert match is not None
        assert match["status"] == "INGESTED"
        assert match["commit_sha"] == "c0ffee123456"

        # 3. Snapshot -> verify resolves record
        res_snap = client.get(f"/api/v1/ingest/snapshot/{actual_repo_id}")
        assert res_snap.status_code == 200
        snap_data = res_snap.json()
        assert snap_data["repository_id"] == actual_repo_id
        assert snap_data["commit_sha"] == "c0ffee123456"

        # 4. File tree
        res_tree = client.get(f"/api/v1/ingest/file-tree?repo_id={actual_repo_id}")
        assert res_tree.status_code == 200
        tree_data = res_tree.json()
        assert tree_data["repository_id"] == actual_repo_id
        assert any(node["name"] == "app.py" for node in tree_data["tree"])

        # 5. File content
        res_content = client.get(f"/api/v1/ingest/file-content?repo_id={actual_repo_id}&file_path=app.py")
        assert res_content.status_code == 200
        content_data = res_content.json()
        assert "def start()" in content_data["content"]
        assert content_data["repository_id"] == actual_repo_id

        # 6. Investigation with repo_id -> verify does NOT fail with 'repository not registered'
        res_inv = client.post(
            "/api/v1/investigation/run",
            json={
                "question": "How does the app start?",
                "repo_id": actual_repo_id,
            },
        )
        assert res_inv.status_code == 200
        inv_data = res_inv.json()
        assert "not registered" not in inv_data.get("summary", "").lower()
        assert inv_data["repository_id"] == actual_repo_id


def test_full_zip_ingestion_lifecycle_consistency(client):
    """Uploaded ZIP archive supports full lifecycle: ingest -> list -> snapshot -> file-tree -> file-content."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pkg/main.py", "def run():\n    return 'hello from zip'\n")
        zf.writestr("pkg/__init__.py", "")
    zip_bytes = buf.getvalue()

    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        # 1. Upload & Ingest ZIP
        res_upload = client.post(
            "/api/v1/ingest/upload-zip",
            files={"file": ("myproject.zip", zip_bytes, "application/zip")},
            data={"display_name": "My Project ZIP"},
        )
        assert res_upload.status_code == 200
        upload_data = res_upload.json()
        zip_repo_id = upload_data["repository_id"]
        assert zip_repo_id.startswith("repo:archive_")

        # 2. List repositories -> verify status is INGESTED
        res_list = client.get("/api/v1/ingest/repositories")
        assert res_list.status_code == 200
        repos = res_list.json()
        match = next((r for r in repos if r["id"] == zip_repo_id), None)
        assert match is not None
        assert match["status"] == "INGESTED"

        # 3. Snapshot -> verify resolves record
        res_snap = client.get(f"/api/v1/ingest/snapshot/{zip_repo_id}")
        assert res_snap.status_code == 200
        snap = res_snap.json()
        assert snap["repository_id"] == zip_repo_id
        assert snap["graph_name"] == match["graph_name"]

        # 4. File tree
        res_tree = client.get(f"/api/v1/ingest/file-tree?repo_id={zip_repo_id}")
        assert res_tree.status_code == 200
        tree = res_tree.json()
        assert tree["repository_id"] == zip_repo_id
        assert tree["total_files"] >= 1

        # 5. File content -> use actual path from tree
        first_file = next(node["path"] for node in tree["tree"] if node["type"] == "file" and node["name"] == "main.py")
        res_content = client.get(f"/api/v1/ingest/file-content?repo_id={zip_repo_id}&file_path={first_file}")
        assert res_content.status_code == 200
        content = res_content.json()
        assert "hello from zip" in content["content"]
