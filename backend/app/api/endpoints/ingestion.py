"""Repository ingestion and multi-repository management API endpoints."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE
from backend.app.ingestion.engine import IngestionReport, RepositoryIngestionEngine
from backend.app.sources.github_fetcher import GitHubRepoFetcher
from backend.app.sources.github_metadata import GitHubMetadataCollector
from backend.app.sources.models import (
    PublicGitHubUrl,
    RegisterRepositoryRequest,
    RepositoryRecord,
    SourceMetadataOutput,
    SourceType,
)
from backend.app.sources.registry import repo_registry

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
    repo_id: Optional[str] = Field(
        default=None,
        description="Optional repository identifier in registry.",
    )


class OnboardRepoRequest(BaseModel):
    repo_id: Optional[str] = Field(default=None, description="Registered repo ID to clone and ingest")
    url_or_path: Optional[str] = Field(default=None, description="Direct URL or path to onboard")
    source_type: Optional[SourceType] = Field(default=None, description="local or github")
    display_name: Optional[str] = Field(default=None)


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
        report = engine.ingest(
            repo_path=str(path_obj),
            graph_name=payload.graph_name,
            repo_id=payload.repo_id,
        )
        return report
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/register", response_model=RepositoryRecord)
def register_repository(payload: RegisterRepositoryRequest) -> RepositoryRecord:
    """Registers a new repository source (local path or public GitHub HTTPS URL) without ingesting immediately."""
    try:
        if payload.source_type == SourceType.GITHUB:
            return repo_registry.register_github_repository(
                github_url=payload.url_or_path,
                display_name=payload.display_name,
                custom_graph_name=payload.custom_graph_name,
            )
        else:
            return repo_registry.register_local_repository(
                local_path=payload.url_or_path,
                display_name=payload.display_name,
                custom_graph_name=payload.custom_graph_name,
            )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Registration failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/clone-and-ingest", response_model=IngestionReport)
def clone_and_ingest(payload: OnboardRepoRequest) -> IngestionReport:
    """Safely clones a public GitHub repo (or reads local path) and ingests it into an isolated graph."""
    # 1. Resolve or register repository record
    record: Optional[RepositoryRecord] = None
    if payload.repo_id:
        record = repo_registry.get_repository(payload.repo_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Repository '{payload.repo_id}' not found.")
    elif payload.url_or_path:
        source_type = payload.source_type or (
            SourceType.GITHUB if payload.url_or_path.strip().startswith("http") else SourceType.LOCAL
        )
        try:
            if source_type == SourceType.GITHUB:
                record = repo_registry.register_github_repository(
                    github_url=payload.url_or_path,
                    display_name=payload.display_name,
                )
            else:
                record = repo_registry.register_local_repository(
                    local_path=payload.url_or_path,
                    display_name=payload.display_name,
                )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    else:
        raise HTTPException(status_code=400, detail="Must provide repo_id or url_or_path.")

    # 2. Prepare checkout path and collect metadata
    checkout_path: Path
    github_meta: Optional[Dict[str, Any]] = None

    if record.source_type == SourceType.GITHUB:
        try:
            val_url = PublicGitHubUrl.parse_and_validate(record.url_or_path)
            fetcher = GitHubRepoFetcher()
            checkout_path, commit_sha = fetcher.clone_or_update(val_url)
            record.commit_sha = commit_sha

            # Collect public GitHub metadata (PRs and reviews)
            collector = GitHubMetadataCollector()
            meta, cap = collector.collect_metadata(val_url.owner, val_url.repo)
            github_meta = meta
            record.capabilities = [cap]
            if cap.known_gaps:
                record.known_gaps = list(cap.known_gaps)
        except Exception as e:
            logger.error("Failed fetching GitHub repository: %s", e)
            record.status = "FAILED"
            repo_registry.update_repository(record)
            raise HTTPException(status_code=500, detail=f"Failed fetching GitHub repository: {str(e)}")
    else:
        checkout_path = Path(record.url_or_path).resolve()
        if not checkout_path.exists():
            raise HTTPException(status_code=400, detail=f"Path '{checkout_path}' does not exist.")

    # 3. Ingest into isolated graph
    try:
        engine = RepositoryIngestionEngine(graph_client)
        report = engine.ingest(
            repo_path=str(checkout_path),
            graph_name=record.graph_name,
            repo_id=record.id,
            github_metadata=github_meta,
        )
        return report
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/refresh/{repo_id}", response_model=IngestionReport)
def refresh_repository(repo_id: str) -> IngestionReport:
    """Refreshes a registered repository to its latest commit."""
    return clone_and_ingest(OnboardRepoRequest(repo_id=repo_id))


@router.get("/repositories", response_model=List[RepositoryRecord])
def list_repositories() -> List[RepositoryRecord]:
    """Lists all registered and ingested repositories with their graph mappings and status."""
    return repo_registry.list_repositories()


@router.get("/sources/{repo_id}", response_model=SourceMetadataOutput)
def get_source_metadata(repo_id: str) -> SourceMetadataOutput:
    """Inspects discovered source capabilities, data freshness, and known gaps for a repository."""
    record = repo_registry.get_repository(repo_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    return SourceMetadataOutput(
        repository_id=record.id,
        repository_name=record.name,
        graph_name=record.graph_name,
        commit_sha=record.commit_sha,
        sources=record.capabilities,
        known_gaps=record.known_gaps,
    )


@router.get("/modules", response_model=List[ModuleSuggestion])
def list_modules(
    query: Optional[str] = Query(default=None, description="Prefix or substring search for modules"),
    limit: int = Query(default=50, ge=1, le=200),
    graph_name: Optional[str] = None,
    repo_id: Optional[str] = None,
) -> List[ModuleSuggestion]:
    """Returns available modules in the active graph for autocomplete and investigation targets."""
    target_graph = graph_name
    if not target_graph and repo_id:
        rec = repo_registry.get_repository(repo_id)
        if rec:
            target_graph = rec.graph_name

    target_graph = target_graph or graph_client.primary_graph_name

    try:
        if query:
            res = graph_client.query(
                f"""
                MATCH (m:{LABEL_MODULE})
                WHERE m.name CONTAINS $q OR m.id CONTAINS $q
                RETURN m.id, m.name, m.path
                LIMIT $limit
                """,
                params={"q": query.strip(), "limit": limit},
                graph_name=target_graph,
            )
        else:
            res = graph_client.query(
                f"""
                MATCH (m:{LABEL_MODULE})
                RETURN m.id, m.name, m.path
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
