"""Unit tests for FastAPI health and configuration."""

from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app

client = TestClient(app)


def test_liveness_endpoint_returns_ok():
    """Verify that /api/v1/health returns 200 and process details."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["app_name"] == settings.APP_NAME
    assert data["app_version"] == settings.APP_VERSION
    assert data["app_env"] == settings.APP_ENV


def test_correlation_id_middleware():
    """Verify that X-Request-ID and X-Response-Time-Ms headers are injected."""
    custom_id = "test-corr-id-12345"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
    assert "X-Response-Time-Ms" in response.headers


def test_cors_headers_handling():
    """Verify CORS headers for allowed origins."""
    origin = settings.cors_origin_list[0]
    response = client.get(
        "/api/v1/health",
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_production_mode_security_hardening(monkeypatch):
    """Verify that in production mode, docs are disabled and TrustedHostMiddleware blocks untrusted hosts."""
    monkeypatch.setattr(settings, "APP_ENV", "production")
    from backend.app.main import create_app

    prod_app = create_app()
    prod_client = TestClient(prod_app)

    # 1. Docs and redoc return 404
    docs_resp = prod_client.get("/api/docs")
    assert docs_resp.status_code == 404
    redoc_resp = prod_client.get("/api/redoc")
    assert redoc_resp.status_code == 404

    # 2. Trusted host succeeds
    trusted_resp = prod_client.get("/api/v1/health", headers={"Host": "localhost"})
    assert trusted_resp.status_code == 200

    # 3. Untrusted Host header is rejected by TrustedHostMiddleware (400 Invalid Host Header)
    untrusted_resp = prod_client.get("/api/v1/health", headers={"Host": "evil-attacker.com"})
    assert untrusted_resp.status_code == 400
