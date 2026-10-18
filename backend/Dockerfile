# ==============================================================================
# NexusAct (GAF) — Backend Production Dockerfile
# Base: python:3.12-slim  (matches local dev environment)
# ==============================================================================
# Build:
#   docker build -t nexusact-backend ./backend
# Run (standalone, requires FALKORDB_HOST env):
#   docker run --rm -p 8000:8000 \
#     -e FALKORDB_HOST=<host> \
#     -e FALKORDB_PORT=6379 \
#     nexusact-backend
# ==============================================================================

FROM python:3.12-slim AS base

# ── System dependencies ───────────────────────────────────────────────────────
# git is required for repository cloning (sources.github_fetcher)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root application user ─────────────────────────────────────────
RUN addgroup --system nexusact && adduser --system --ingroup nexusact --home /home/nexusact nexusact

WORKDIR /app

# ── Application source and build files ────────────────────────────────────────
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
COPY mcp_server/ ./mcp_server/
COPY .env.example .env.example

# Install uv for fast dependency resolution, then install runtime deps.
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Writable cache directory for repo clones
RUN mkdir -p /home/nexusact/.cache/nexusact && \
    chown -R nexusact:nexusact /home/nexusact /app

USER nexusact

# ── Runtime configuration ─────────────────────────────────────────────────────
# All values are overridden via environment variables or secrets at runtime.
# These defaults are safe for local container use ONLY.
ENV HOME=/home/nexusact \
    APP_ENV=production \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000 \
    FALKORDB_HOST=falkordb \
    FALKORDB_PORT=6379 \
    FALKORDB_PRIMARY_GRAPH=nexusact_main \
    CORS_ORIGINS=http://localhost:5173 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --log-level info"]
