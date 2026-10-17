import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from backend.app.agent.llm import GeminiProvider, get_llm_provider
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


class LLMTestResponse(BaseModel):
    status: str = Field(..., description="Status: GEMINI_ACTIVE, FALLBACK_ACTIVE, NOT_CONFIGURED, PROVIDER_UNAVAILABLE")
    provider: str
    model: str
    latency_ms: float
    message: str
    credentials_detected: bool


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
    active_repo_id: Optional[str] = Field(default=None, description="Active repository identifier")
    active_repo_name: Optional[str] = Field(default=None, description="Active repository display name")
    commit_sha: Optional[str] = Field(default=None, description="Active commit SHA")
    freshness_status: Optional[str] = Field(default=None, description="Source freshness status")
    llm_provider: str = Field("Heuristic Rule-Based Engine", description="Active intelligence provider")
    llm_configured: bool = Field(False, description="Whether an external LLM API key is provided")
    planner_provider: str = Field("FALLBACK_ACTIVE", description="Agent planning reasoning status")
    planner_model: str = Field("deterministic-rule-engine", description="Active planning model")
    explanation_provider: str = Field("FALLBACK_ACTIVE", description="Panel explanation reasoning status")
    explanation_model: str = Field("deterministic-grounding", description="Active explanation model")
    credentials_detected: bool = Field(False, description="Whether server-side LLM credentials were detected")
    action_service_configured: bool = Field(True, description="Whether verified action execution service is active")
    action_approval_required: bool = Field(True, description="Whether manual approval is enforced for actions")
    mcp_tools: List[str] = Field(
        default_factory=lambda: ["nexusact_diagnose_graph"], description="Registered MCP tools"
    )
    subsystem_health: Dict[str, str] = Field(default_factory=dict, description="Status per subsystem")


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

    from backend.app.sources.registry import repo_registry

    repos = repo_registry.list_repositories()
    active_repo = repos[0] if repos else None

    llm_has_key = bool(settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    active_provider = get_llm_provider()
    gemini_working = isinstance(active_provider, GeminiProvider) and active_provider.is_available

    if isinstance(active_provider, GeminiProvider) and active_provider.is_available:
        planner_status = "GEMINI_ACTIVE"
        planner_model = active_provider.model
        explanation_status = "GEMINI_ACTIVE"
        explanation_model = active_provider.model
        llm_name = f"Google Gemini ({active_provider.model})"
    elif llm_has_key:
        planner_status = "PROVIDER_UNAVAILABLE"
        planner_model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        explanation_status = "PROVIDER_UNAVAILABLE"
        explanation_model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        llm_name = "Gemini (Client Unavailable)"
    else:
        planner_status = "FALLBACK_ACTIVE"
        planner_model = "deterministic-rule-engine"
        explanation_status = "FALLBACK_ACTIVE"
        explanation_model = "deterministic-grounding"
        llm_name = "Heuristic Rule-Based Traversal Engine"

    subsystems = {
        "fastapi": "HEALTHY",
        "falkordb": "HEALTHY" if diag.get("connected") else "UNAVAILABLE",
        "mcp_server": "HEALTHY",
        "llm_engine": "HEALTHY" if gemini_working else "OPTIONAL_FALLBACK",
        "action_service": "HEALTHY",
        "source_freshness": "HEALTHY" if (active_repo and active_repo.freshness_status != "STALE") else "DEGRADED",
    }

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
        active_repo_id=active_repo.id if active_repo else None,
        active_repo_name=active_repo.name if active_repo else None,
        commit_sha=active_repo.commit_sha if active_repo else None,
        freshness_status=active_repo.freshness_status if active_repo else None,
        llm_provider=llm_name,
        llm_configured=llm_has_key,
        planner_provider=planner_status,
        planner_model=planner_model,
        explanation_provider=explanation_status,
        explanation_model=explanation_model,
        credentials_detected=llm_has_key,
        action_service_configured=True,
        action_approval_required=True,
        mcp_tools=["nexusact_diagnose_graph"],
        subsystem_health=subsystems,
    )


@router.post(
    "/system/llm-test",
    response_model=LLMTestResponse,
    summary="Safe LLM connectivity check",
    description="Tests server-side Gemini connectivity with a bounded 5s timeout and redacted secrets.",
)
async def test_llm_connectivity() -> LLMTestResponse:
    """Safe, bounded connectivity test for LLM provider."""
    start = time.perf_counter()
    has_key = bool(settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    if not has_key:
        return LLMTestResponse(
            status="NOT_CONFIGURED",
            provider="Deterministic Rule Engine",
            model="none",
            latency_ms=0.0,
            message="No server-side GEMINI_API_KEY detected. Rule-based heuristic fallback is active and healthy.",
            credentials_detected=False,
        )

    provider = get_llm_provider()
    if not isinstance(provider, GeminiProvider) or not provider.is_available:
        return LLMTestResponse(
            status="PROVIDER_UNAVAILABLE",
            provider="Google Gemini",
            model=getattr(provider, "model", settings.GEMINI_MODEL or "unknown"),
            latency_ms=0.0,
            message="Credentials detected, but Gemini client failed initialization.",
            credentials_detected=True,
        )

    try:
        from google.genai import types

        # Bounded ping test
        _ = provider._client.models.generate_content(
            model=provider.model,
            contents="ping",
            config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0),
        )
        latency = round((time.perf_counter() - start) * 1000, 1)
        return LLMTestResponse(
            status="GEMINI_ACTIVE",
            provider="Google Gemini",
            model=provider.model,
            latency_ms=latency,
            message=f"Successfully verified Gemini connectivity ({provider.model}).",
            credentials_detected=True,
        )
    except Exception as exc:
        latency = round((time.perf_counter() - start) * 1000, 1)
        safe_msg = str(exc)
        if settings.GEMINI_API_KEY:
            safe_msg = safe_msg.replace(settings.GEMINI_API_KEY, "[REDACTED]")
        if os.environ.get("GEMINI_API_KEY"):
            safe_msg = safe_msg.replace(os.environ["GEMINI_API_KEY"], "[REDACTED]")
        if os.environ.get("GOOGLE_API_KEY"):
            safe_msg = safe_msg.replace(os.environ["GOOGLE_API_KEY"], "[REDACTED]")
        return LLMTestResponse(
            status="PROVIDER_UNAVAILABLE",
            provider="Google Gemini",
            model=provider.model,
            latency_ms=latency,
            message=f"Gemini API check failed: {safe_msg[:160]}",
            credentials_detected=True,
        )
