"""Repository ingestion API endpoints."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE, LABEL_REPOSITORY
from backend.app.ingestion.engine import IngestionReport, RepositoryIngestionEngine

logger = logging.getLogger("nexusact.api.ingestion")
router = APIRouter(prefix="/ingest", tags=["Repository Ingestion"])


class IngestRequest(BaseModel):
    repository_path: Optional[str] = Field(
        default=None,
        description="Path to local Git repository. Defaults to NEXUSACT_REPOSITORY_PATH if omitted.",
    )
    graph_name: Optional[str] = Field(
        default=None,
        description="FalkorDB target graph name. Defaults to primary graph.",
    )


class ModuleSuggestion(BaseModel):
    id: str
    name: str
    file_path: Optional[str] = None


@router.post("", response_model=IngestionReport)
def trigger_ingestion(payload: IngestRequest) -> IngestionReport:
    """Ingests a local Git repository into FalkorDB via AST and commit extraction."""
    repo_path = payload.repository_path or settings.NEXUSACT_REPOSITORY_PATH
    path_obj = Path(repo_path).resolve()

    if not path_obj.exists() or not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path '{repo_path}' does not exist or is not a directory.",
        )

    try:
        engine = RepositoryIngestionEngine(graph_client)
        report = engine.ingest(repo_path=str(path_obj), graph_name=payload.graph_name)
        return report
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/repositories", response_model=List[Dict[str, Any]])
def list_repositories(graph_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists ingested repositories recorded in the graph."""
    target_graph = graph_name or graph_client.primary_graph_name
    try:
        res = graph_client.query(
            f"MATCH (r:{LABEL_REPOSITORY}) RETURN r.id, r.name, r.commit_sha, r.ingested_at",
            graph_name=target_graph,
        )
        repos = []
        for row in res:
            repos.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "commit_sha": row[2],
                    "ingested_at": row[3],
                }
            )
        return repos
    except Exception as e:
        logger.error("Failed to list repositories: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules", response_model=List[ModuleSuggestion])
def list_modules(
    query: Optional[str] = Query(default=None, description="Prefix or substring search for modules"),
    limit: int = Query(default=50, ge=1, le=200),
    graph_name: Optional[str] = None,
) -> List[ModuleSuggestion]:
    """Returns available modules in the graph for autocomplete and investigation targets."""
    target_graph = graph_name or graph_client.primary_graph_name
    try:
        if query:
            res = graph_client.query(
                f"""
                MATCH (m:{LABEL_MODULE})
                WHERE m.name CONTAINS $q OR m.id CONTAINS $q
                RETURN m.id, m.name, m.file_path
                LIMIT $limit
                """,
                params={"q": query.strip(), "limit": limit},
                graph_name=target_graph,
            )
        else:
            res = graph_client.query(
                f"""
                MATCH (m:{LABEL_MODULE})
                RETURN m.id, m.name, m.file_path
                ORDER BY m.name ASC
                LIMIT $limit
                """,
                params={"limit": limit},
                graph_name=target_graph,
            )

        modules = []
        for row in res:
            modules.append(ModuleSuggestion(id=row[0], name=row[1] or row[0], file_path=row[2]))
        return modules
    except Exception as e:
        logger.error("Failed to list modules: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
