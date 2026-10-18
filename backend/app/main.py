"""NexusAct FastAPI Backend Application Entry Point."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List
from urllib.parse import urlparse

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.errors import ErrorResponse, NexusActError
from backend.app.core.logging import logger
from backend.app.graph.client import graph_client
from backend.app.graph.initialization import initialize_schema


def _extract_hosts_from_origins(origins: List[str]) -> List[str]:
    """Derive allowed Host header values from the configured CORS origin list."""
    hosts = set()
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.hostname:
            hosts.add(parsed.hostname)
            if parsed.port:
                hosts.add(f"{parsed.hostname}:{parsed.port}")
    # Local/test/internal hosts plus Railway's fixed health-check host. No wildcard hosts.
    hosts.update(
        [
            "localhost",
            "127.0.0.1",
            "backend",
            "testserver",
            "localhost:8000",
            "127.0.0.1:8000",
            "healthcheck.railway.app",
        ]
    )
    return list(hosts)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: startup initialization and graceful shutdown."""
    logger.info(
        "Starting up %s (version: %s, env: %s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )

    # 1. Check FalkorDB connection on startup
    if graph_client.ping():
        logger.info("FalkorDB connection confirmed on %s:%d", settings.FALKORDB_HOST, settings.FALKORDB_PORT)
        try:
            # Idempotently ensure base indices and metadata exist
            init_res = initialize_schema(graph_client)
            logger.info("Primary schema initialization: %s", init_res["status"])
            if settings.PUBLIC_DEMO_MODE:
                # Seed only an empty graph; existing graph data is never deleted or overwritten.
                try:
                    from backend.app.graph.public_demo_seed import seed_public_demo_graph

                    seed_summary = seed_public_demo_graph(graph_client)
                    logger.info("Public demo graph bootstrap: %s", seed_summary)
                except Exception as seed_exc:
                    logger.warning("Public demo graph bootstrap skipped/failed: %s", seed_exc)
        except Exception as exc:
            logger.warning("FalkorDB schema initialization warning: %s", exc)
    else:
        logger.warning(
            "FalkorDB is NOT reachable on %s:%d at startup. Backend running in degraded mode.",
            settings.FALKORDB_HOST,
            settings.FALKORDB_PORT,
        )

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    graph_client.close()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application."""
    is_production = settings.APP_ENV == "production"

    application = FastAPI(
        title=f"{settings.APP_NAME} API",
        description="Graph-native AI engineering agent API for repository analysis and connected intelligence.",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        # Disable interactive API docs in production (reduce attack surface)
        docs_url=None if is_production else "/api/docs",
        redoc_url=None if is_production else "/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # 1. CORS Configuration (Explicit origins only, no wildcard)
    logger.info("Configured CORS allowed origins: %s", settings.cors_origin_list)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 1b. TrustedHostMiddleware — prevents Host header injection in production
    if is_production:
        allowed_hosts = _extract_hosts_from_origins(settings.cors_origin_list)
        logger.info("Production mode: enforcing TrustedHostMiddleware hosts=%s", allowed_hosts)
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # 2. Request Correlation ID & Performance Middleware
    @application.middleware("http")
    async def request_correlation_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response

    # 3. Application Exception Handlers
    @application.exception_handler(NexusActError)
    async def nexusact_error_handler(request: Request, exc: NexusActError):
        req_id = getattr(request.state, "request_id", None)
        err_payload = ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.message,
            details=exc.details,
            request_id=req_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err_payload.model_dump(),
        )

    # 4. Root probes for standard container/cloud load balancer checks
    from backend.app.api.endpoints import health

    application.include_router(health.router)

    # 5. Include API v1 routers
    application.include_router(api_router)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=(settings.APP_ENV == "development"),
    )
