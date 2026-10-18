"""Global pytest configuration ensuring automated tests run in deterministic test isolation."""

import pytest

from backend.app.core.config import settings


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """Guarantees tests use deterministic baseline settings regardless of user's personal .env keys."""
    # Preserve explicit overrides if a test patches these specifically
    monkeypatch.setattr(settings, "APP_ENV", "testing")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "none")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "PUBLIC_DEMO_MODE", False)
