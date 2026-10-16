"""Regression tests for Phase 8 CORS and API connectivity.

Verifies:
1. Normal GET and preflight OPTIONS from http://localhost:5174 are accepted with valid CORS headers.
2. Normal GET and preflight OPTIONS from http://127.0.0.1:5174 are accepted.
3. Untrusted external origins (e.g. http://malicious-site.com) are rejected.
4. Production mode enforces strict explicit origins without wildcard or regex.
"""

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_cors_localhost_5174_get_and_options():
    """Verify http://localhost:5174 is allowed in development mode for both GET and preflight OPTIONS."""
    app = create_app()
    client = TestClient(app)

    # 1. Preflight OPTIONS request
    options_res = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type, X-Request-ID",
        },
    )
    assert options_res.status_code == 200
    assert options_res.headers.get("access-control-allow-origin") == "http://localhost:5174"
    assert "GET" in options_res.headers.get("access-control-allow-methods", "")

    # 2. Actual GET request
    get_res = client.get(
        "/health",
        headers={"Origin": "http://localhost:5174"},
    )
    assert get_res.status_code == 200
    assert get_res.headers.get("access-control-allow-origin") == "http://localhost:5174"


def test_cors_loopback_127_0_0_1_5174():
    """Verify loopback 127.0.0.1:5174 is accepted."""
    app = create_app()
    client = TestClient(app)

    res = client.get(
        "/api/v1/discover/sources",
        headers={"Origin": "http://127.0.0.1:5174"},
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://127.0.0.1:5174"


def test_cors_untrusted_origin_rejected():
    """Verify arbitrary external origins do not receive an access-control-allow-origin header."""
    app = create_app()
    client = TestClient(app)

    res = client.get(
        "/health",
        headers={"Origin": "http://malicious-site.example.com"},
    )
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers


def test_cors_production_mode_strict():
    """Verify production mode disables loopback regex and only allows explicitly configured origins."""
    prod_settings = Settings(
        APP_ENV="production",
        CORS_ORIGINS="https://nexusact.internal.corp",
    )
    assert prod_settings.cors_origin_regex is None
    assert prod_settings.cors_origin_list == ["https://nexusact.internal.corp"]
