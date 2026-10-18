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


def test_public_demo_mode_blocks_clone_and_ingest(client):
    with patch.object(settings, "PUBLIC_DEMO_MODE", True):
        res = client.post(
            "/api/v1/ingest/clone-and-ingest",
            json={"url_or_path": "https://github.com/example/repo"},
        )
        assert res.status_code == 403
        assert "disabled in public demo mode" in res.json()["detail"]


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
