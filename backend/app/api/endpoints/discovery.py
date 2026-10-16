"""Universal public-data discovery and Ask GAF endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.agent.discovery_planner import (
    UniversalDiscoveryPlanner,
    UniversalInvestigationResult,
)
from backend.app.sources.connector_registry import (
    ConnectorQuery,
    ConnectorRegistry,
)
from backend.app.sources.graph_persister import PublicGraphPersister

logger = logging.getLogger("nexusact.api.discovery")

router = APIRouter(prefix="/discover")
planner = UniversalDiscoveryPlanner()
persister = PublicGraphPersister()


class AskGafRequest(BaseModel):
    """Payload to trigger Universal Ask GAF investigation."""

    question: str = Field(..., min_length=3, description="Natural language investigation question.")
    selected_sources: list[str] | None = Field(default=None, description="Explicit source IDs to query.")
    max_results: int = Field(default=5, ge=1, le=20, description="Max results per queried source.")
    input_mode: str = Field(
        default="public", description="Investigation input mode: 'public', 'repository', or 'combined'."
    )
    repository_id: str | None = Field(
        default=None, description="Target repository ID when input_mode is 'repository' or 'combined'."
    )
    graph_name: str | None = Field(default=None, description="FalkorDB graph name for the target repository.")
    commit_sha: str | None = Field(default=None, description="Source revision / commit SHA for the target repository.")


class SearchSourceRequest(BaseModel):
    """Payload to search a specific public connector."""

    source_id: str
    query_text: str
    entity_types: list[str] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=20)


@router.get("/sources", response_model=dict[str, Any])
def list_sources() -> dict[str, Any]:
    """Lists all approved public source connectors and their health states."""
    try:
        health_info = ConnectorRegistry.health_status()
        return {
            "sources": health_info,
            "total_connectors": len(health_info),
        }
    except Exception as exc:
        logger.error("Failed querying source connector status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ask-gaf", response_model=UniversalInvestigationResult)
def ask_universal_gaf(req: AskGafRequest) -> UniversalInvestigationResult:
    """Investigates a natural-language question across approved public sources or repository graphs."""
    try:
        plan = planner.create_plan(
            question=req.question,
            input_mode=req.input_mode,
            repository_id=req.repository_id,
            graph_name=req.graph_name,
            commit_sha=req.commit_sha,
        )
        if req.selected_sources:
            plan.selected_source_ids = req.selected_sources
        if req.max_results:
            plan.max_results_per_source = req.max_results

        result = planner.execute_investigation(
            req.question,
            plan_override=plan,
            input_mode=req.input_mode,
            repository_id=req.repository_id,
            graph_name=req.graph_name,
            commit_sha=req.commit_sha,
        )
        try:
            persister.save_investigation(
                investigation_id=result.investigation_id,
                question=result.question,
                summary=result.summary,
                approach=result.approach,
                sources=result.plan.selected_source_ids,
                entities=result.entities,
                next_action=result.next_action,
                input_mode=result.input_mode,
                repository_id=result.repository_id,
                graph_name=result.graph_name,
                commit_sha=result.commit_sha,
            )
        except Exception as save_exc:
            logger.warning("Could not persist investigation memory: %s", save_exc)
        return result
    except Exception as exc:
        logger.error("Ask GAF execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Universal Ask GAF execution failed: {exc}")


@router.post("/search", response_model=dict[str, Any])
def search_source(req: SearchSourceRequest) -> dict[str, Any]:
    """Executes a bounded search directly against a specific source connector."""
    conn = ConnectorRegistry.get(req.source_id)
    if not conn:
        avail = ConnectorRegistry.all_source_ids()
        raise HTTPException(
            status_code=404,
            detail=f"Source connector '{req.source_id}' is not registered. Available: {avail}",
        )

    query = ConnectorQuery(
        query_text=req.query_text,
        entity_types=req.entity_types,
        max_results=req.max_results,
    )
    result = conn.search(query)

    # Persist into FalkorDB
    persister.persist_records(result.records)

    return {
        "source_id": result.source_id,
        "count": len(result.records),
        "total_available": result.total_available,
        "records": [
            {
                "id": f"{r.source_id}:{r.external_id}",
                "entity_type": r.entity_type,
                "external_id": r.external_id,
                "canonical_url": r.canonical_url,
                "data": r.data,
                "relationships_count": len(r.relationships),
            }
            for r in result.records
        ],
        "coverage_notes": result.coverage_notes,
        "error": result.error,
    }


@router.get("/subgraph", response_model=dict[str, Any])
def get_public_subgraph(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Retrieves nodes and edges from the public knowledge graph for visualization."""
    return persister.get_subgraph(limit=limit)


@router.get("/path", response_model=dict[str, Any])
def get_public_path(
    start_id: str = Query(..., description="Source entity ID"),
    target_id: str = Query(..., description="Target entity ID"),
    max_hops: int = Query(default=3, ge=1, le=4),
) -> dict[str, Any]:
    """Finds evidence-supported paths between two public entities."""
    paths = persister.find_path(start_id, target_id, max_hops=max_hops)
    return {
        "start_id": start_id,
        "target_id": target_id,
        "paths": paths,
        "total_paths": len(paths),
    }


@router.get("/investigations", response_model=dict[str, Any])
def list_investigations(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    """Lists saved public investigations from FalkorDB graph memory."""
    items = persister.list_saved_investigations(limit=limit)
    return {"investigations": items, "total": len(items)}


class ConfirmActionRequest(BaseModel):
    action_id: str


@router.post("/actions/confirm", response_model=dict[str, Any])
def confirm_action(req: ConfirmActionRequest) -> dict[str, Any]:
    """Confirms and executes a recommended investigation action in FalkorDB."""
    ok = persister.confirm_action(req.action_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Action '{req.action_id}' not found.")
    return {
        "action_id": req.action_id,
        "status": "CONFIRMED",
        "message": "Action confirmed and persisted in graph memory.",
    }
