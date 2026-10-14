"""Central API v1 router for NexusAct."""

from fastapi import APIRouter

from backend.app.api.endpoints import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["System & Health"])
