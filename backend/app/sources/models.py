"""Source discovery, capabilities, and repository onboarding data models."""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    LOCAL = "local"
    GITHUB = "github"
    ARCHIVE = "archive"


class CollectionStatus(str, Enum):
    COLLECTED = "COLLECTED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    PENDING = "PENDING"


class PublicGitHubUrl(BaseModel):
    """Validated public GitHub repository URL without embedded credentials."""

    raw_url: str
    owner: str
    repo: str
    canonical_url: str

    @classmethod
    def parse_and_validate(cls, raw_url: str) -> "PublicGitHubUrl":
        """
        Validates that a URL is a legitimate HTTPS public GitHub repository URL.
        Rejects:
        - Non-HTTPS URLs (e.g. http://, git://, ssh://)
        - Non-github.com hosts
        - Embedded credentials (e.g. https://user:pass@github.com/...)
        - Malformed or unsupported paths
        """
        trimmed = raw_url.strip()
        parsed = urlparse(trimmed)

        if parsed.scheme.lower() != "https":
            raise ValueError(f"Only HTTPS URLs are permitted. Received scheme: '{parsed.scheme}'.")

        netloc = parsed.netloc.lower()
        if "@" in netloc:
            raise ValueError("URLs with embedded credentials (user:password@) are strictly forbidden.")

        if netloc in ("github.com", "www.github.com"):
            host = "github.com"
        else:
            raise ValueError(f"Only 'github.com' is allowed as public git host. Received host: '{parsed.netloc}'.")

        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) != 2:
            raise ValueError(f"Expected repository path format '/{{owner}}/{{repository}}'. Received: '{parsed.path}'.")

        owner, repo = path_parts[0], path_parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

        ident_pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
        if not ident_pattern.match(owner):
            raise ValueError(f"Invalid characters in repository owner name: '{owner}'.")
        if not ident_pattern.match(repo):
            raise ValueError(f"Invalid characters in repository name: '{repo}'.")

        canonical = f"https://{host}/{owner}/{repo}"
        return cls(raw_url=trimmed, owner=owner, repo=repo, canonical_url=canonical)


class SourceCapability(BaseModel):
    """Provenance and capability descriptor for a specific discovered data source."""

    source_id: str
    source_type: SourceType
    repository_identifier: str
    data_categories: List[str] = Field(default_factory=list)
    status: CollectionStatus = CollectionStatus.PENDING
    retrieval_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data_freshness: Optional[str] = None
    known_gaps: List[str] = Field(default_factory=list)
    error_details: Optional[str] = None


class SourceSnapshot(BaseModel):
    """Canonical source-snapshot contract binding an investigation to an exact revision and graph."""

    snapshot_id: str
    repository_id: str
    source_type: SourceType
    canonical_source: str
    default_branch: Optional[str] = None
    commit_sha: str
    working_tree_fingerprint: Optional[str] = None
    graph_name: str
    source_checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ingested_at: Optional[str] = None
    parser_version: str = "ast-gaf-v2.0"
    ingestion_status: str = "INGESTED"  # INGESTED | PENDING | FAILED
    module_count: int = 0
    edge_count: int = 0
    known_gaps: List[str] = Field(default_factory=list)
    freshness_status: str = (
        "FRESH"  # FRESH | UPDATED | STALE_SOURCE_UNAVAILABLE | INGESTION_FAILED | SNAPSHOT_UNRESOLVED
    )


class RepositoryRecord(BaseModel):
    """Metadata record for a registered or ingested repository."""

    id: str
    name: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    source_type: SourceType
    url_or_path: str
    canonical_source: Optional[str] = None
    graph_name: str
    default_branch: str = "main"
    commit_sha: str = "HEAD"
    working_tree_fingerprint: Optional[str] = None
    active_snapshot_id: Optional[str] = None
    freshness_status: str = "FRESH"
    source_checked_at: Optional[str] = None
    file_count: int = 0
    module_count: int = 0
    edge_count: int = 0
    contributor_count: int = 0
    commit_count: int = 0
    last_ingested_at: Optional[str] = None
    status: str = "REGISTERED"
    capabilities: List[SourceCapability] = Field(default_factory=list)
    known_gaps: List[str] = Field(default_factory=list)
    parser_warnings: List[str] = Field(default_factory=list)
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_snapshot(self) -> SourceSnapshot:
        """Constructs a canonical SourceSnapshot from this repository record."""
        short_sha = (self.commit_sha or "head")[:8]
        short_fp = (self.working_tree_fingerprint or "clean")[:6]
        slug = re.sub(r"[^A-Za-z0-9_]", "_", self.id.replace("repo:", "")).strip("_")
        snap_id = f"snap_{slug}_{short_sha}_{short_fp}"

        return SourceSnapshot(
            snapshot_id=self.active_snapshot_id or snap_id,
            repository_id=self.id,
            source_type=self.source_type,
            canonical_source=self.url_or_path,
            default_branch=self.default_branch,
            commit_sha=self.commit_sha,
            working_tree_fingerprint=self.working_tree_fingerprint,
            graph_name=self.graph_name,
            source_checked_at=self.source_checked_at or datetime.now(timezone.utc).isoformat(),
            ingested_at=self.last_ingested_at,
            module_count=self.module_count,
            edge_count=self.edge_count,
            known_gaps=list(self.known_gaps),
            freshness_status=self.freshness_status,
        )


class RegisterRepositoryRequest(BaseModel):
    """Payload to register a new repository source."""

    source_type: SourceType
    url_or_path: str = Field(..., description="Local directory path or public GitHub HTTPS URL")
    display_name: Optional[str] = None
    custom_graph_name: Optional[str] = None


class SourceMetadataOutput(BaseModel):
    """Tool output detailing all source capabilities, provenance, and data gaps."""

    repository_id: str
    repository_name: str
    graph_name: str
    commit_sha: str
    working_tree_fingerprint: Optional[str] = None
    active_snapshot_id: Optional[str] = None
    freshness_status: str = "FRESH"
    sources: List[SourceCapability]
    known_gaps: List[str]
    disclaimer: str = (
        "Analysis is bounded by ingested repository and metadata sources. "
        "Missing evidence types reflect data availability, not absence of real activity."
    )
