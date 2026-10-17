"""Central API v1 router for NexusAct."""

from fastapi import APIRouter

from backend.app.api.endpoints import action, discovery, finance, health, ingestion, investigation

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["System & Health"])
api_router.include_router(ingestion.router, tags=["Repository Ingestion"])
api_router.include_router(investigation.router, tags=["Investigation & Graph Tools"])
api_router.include_router(finance.router, tags=["Financial Graph Investigation"])
api_router.include_router(action.router, tags=["Action Execution"])
api_router.include_router(discovery.router, tags=["Universal Discovery & Public Data"])
