"""Health, readiness, and system status endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.graph.client import graph_client
from backend.app.graph.schema import SCHEMA_VERSION

router = APIRouter()


class LivenessResponse(BaseModel):
    status: str = Field("OK", description="Application process status")
    app_name: str = Field(..., description="Application name")
    app_version: str = Field(..., description="Application version")
    app_env: str = Field(..., description="Deployment environment")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Readiness status: READY or DEGRADED/UNAVAILABLE")
    database: Dict[str, Any] = Field(..., description="Database connectivity details")
    schema_version: str = Field(..., description="Active graph schema version")


class SystemStatusResponse(BaseModel):
    app_name: str = Field(..., description="Application title")
    app_env: str = Field(..., description="Environment")
    version: str = Field(..., description="Release version")
    backend_status: str = Field("ONLINE", description="Backend service status")
    falkordb_status: str = Field(..., description="Graph database status")
    falkordb_host: str = Field(..., description="Configured database host")
    falkordb_port: int = Field(..., description="Configured database port")
    primary_graph: str = Field(..., description="Configured primary graph")
    node_count: int = Field(..., description="Total nodes in primary graph")
    edge_count: int = Field(..., description="Total edges in primary graph")
    mcp_server_configured: bool = Field(True, description="Whether MCP server is configured")
    mcp_port: int = Field(..., description="MCP server port")


@router.get(
    "/health",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Application liveness probe",
    description="Returns OK if the FastAPI process is alive, regardless of downstream dependency state.",
)
def get_liveness() -> LivenessResponse:
    """Process liveness probe."""
    return LivenessResponse(
        status="OK",
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        app_env=settings.APP_ENV,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Application and FalkorDB readiness probe",
    description="Honest readiness check verifying active FalkorDB connectivity.",
)
def get_readiness(response: Response) -> ReadinessResponse:
    """Readiness probe verifying actual FalkorDB connectivity."""
    db_connected = graph_client.ping()

    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="UNAVAILABLE",
            database={
                "connected": False,
                "host": settings.FALKORDB_HOST,
                "port": settings.FALKORDB_PORT,
                "graph": settings.FALKORDB_PRIMARY_GRAPH,
                "error": "Cannot ping FalkorDB instance",
            },
            schema_version=SCHEMA_VERSION,
        )

    diag = graph_client.get_graph_diagnostics(settings.FALKORDB_PRIMARY_GRAPH)
    return ReadinessResponse(
        status="READY",
        database={
            "connected": True,
            "host": settings.FALKORDB_HOST,
            "port": settings.FALKORDB_PORT,
            "graph": settings.FALKORDB_PRIMARY_GRAPH,
            "details": diag,
        },
        schema_version=SCHEMA_VERSION,
    )


@router.get(
    "/system/status",
    response_model=SystemStatusResponse,
    summary="Comprehensive system status",
    description="Returns aggregate health metrics for the frontend status dashboard.",
)
def get_system_status() -> SystemStatusResponse:
    """Returns real aggregate system status for the frontend UI."""
    diag = graph_client.get_graph_diagnostics(settings.FALKORDB_PRIMARY_GRAPH)

    db_status = "ONLINE" if diag.get("connected") else "OFFLINE"

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        app_env=settings.APP_ENV,
        version=settings.APP_VERSION,
        backend_status="ONLINE",
        falkordb_status=db_status,
        falkordb_host=settings.FALKORDB_HOST,
        falkordb_port=settings.FALKORDB_PORT,
        primary_graph=settings.FALKORDB_PRIMARY_GRAPH,
        node_count=diag.get("node_count", 0),
        edge_count=diag.get("edge_count", 0),
        mcp_server_configured=True,
        mcp_port=settings.MCP_SERVER_PORT,
    )
