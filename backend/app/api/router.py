"""Central API v1 router for NexusAct."""

from fastapi import APIRouter

from backend.app.api.endpoints import action, discovery, finance, health, ingestion, investigation

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["System & Health"])
api_router.include_router(ingestion.router, tags=["Repository Ingestion"])
api_router.include_router(investigation.router, tags=["Investigation & Graph Intelligence"])
api_router.include_router(investigation.tools_router, tags=["Graph Tools"])
api_router.include_router(investigation.graph_router, tags=["Graph Subgraph"])
api_router.include_router(finance.router, tags=["Financial Graph Investigation"])
api_router.include_router(action.router, tags=["Action Execution"])
api_router.include_router(discovery.router, tags=["Universal Discovery & Public Data"])

# Canonical top-level multi-step investigation loop
api_router.post(
    "/investigate",
    response_model=investigation.InvestigationReport,
    tags=["Investigation & Graph Intelligence"],
    summary="Primary adaptive multi-step investigation loop across active graph",
)(investigation.run_investigation)
