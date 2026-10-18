"""Repository registry for managing multi-repository onboarding, isolation, and metadata."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.core.config import settings
from backend.app.sources.models import (
    CollectionStatus,
    PublicGitHubUrl,
    RepositoryRecord,
    SourceCapability,
    SourceType,
)

logger = logging.getLogger("nexusact.sources.registry")


def get_cache_root() -> Path:
    """Returns the dedicated root directory for cached repositories and registry data outside project source."""
    cache_dir = Path.home() / ".cache" / "nexusact"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def sanitize_graph_name(raw_name: str) -> str:
    """
    Produces a valid, safe FalkorDB graph name (alphanumeric + underscores only, max 30 chars).
    Guarantees prefix 'repo_' for isolation, unless it is the default primary graph.
    """
    clean = re.sub(r"[^A-Za-z0-9_]", "_", raw_name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean:
        clean = "default"
    graph_name = f"repo_{clean}"[:30].rstrip("_")
    return graph_name


class RepositoryRegistry:
    """Manages the registry of known repositories, their graph mappings, and source caches."""

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_dir = get_cache_root()
        self.registry_file = cache_file or (self.cache_dir / "repositories.json")
        self._repositories: Dict[str, RepositoryRecord] = {}
        self._load()
        self._ensure_default_local_repo()

    def _load(self) -> None:
        """Loads repository records from cache file if present."""
        if self.registry_file.exists():
            try:
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                for repo_data in data:
                    rec = RepositoryRecord.model_validate(repo_data)
                    self._repositories[rec.id] = rec
                logger.debug("Loaded %d repository record(s) from %s", len(self._repositories), self.registry_file)
            except Exception as e:
                logger.warning("Failed reading repository registry file %s: %s", self.registry_file, e)

    def _save(self) -> None:
        """Persists repository records to cache file atomically with merge."""
        try:
            # First merge any records written to disk by other workers/processes
            if self.registry_file.exists():
                try:
                    disk_data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                    for repo_data in disk_data:
                        rec = RepositoryRecord.model_validate(repo_data)
                        if rec.id not in self._repositories:
                            self._repositories[rec.id] = rec
                except Exception as read_err:
                    logger.debug("Could not pre-merge registry file %s: %s", self.registry_file, read_err)

            records = [r.model_dump() for r in self._repositories.values()]
            # Write atomically to a PID-tagged temp file then replace target file
            temp_file = self.registry_file.with_name(f"{self.registry_file.name}.tmp.{os.getpid()}")
            temp_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
            temp_file.replace(self.registry_file)
        except Exception as e:
            logger.error("Failed saving repository registry file %s: %s", self.registry_file, e)
            raise RuntimeError(f"Failed to persist repository registry to {self.registry_file}: {e}") from e

    def _ensure_default_local_repo(self) -> None:
        """Ensures the active local workspace repository is always registered with primary graph."""
        local_path = Path(settings.NEXUSACT_REPOSITORY_PATH).resolve()
        repo_id = "repo:local_nexusact"
        if repo_id not in self._repositories:
            record = RepositoryRecord(
                id=repo_id,
                name="NexusAct (Local Workspace)",
                source_type=SourceType.LOCAL,
                url_or_path=str(local_path),
                graph_name=settings.FALKORDB_PRIMARY_GRAPH,
                default_branch="master",
                commit_sha="HEAD",
                status="REGISTERED",
                capabilities=[
                    SourceCapability(
                        source_id="src:local_git",
                        source_type=SourceType.LOCAL,
                        repository_identifier=repo_id,
                        data_categories=["code_ast", "git_history"],
                        status=CollectionStatus.COLLECTED,
                        known_gaps=["PR peer review records unavailable in local Git history"],
                    )
                ],
                known_gaps=["Local git log does not contain GitHub peer PR reviews"],
            )
            self._repositories[repo_id] = record
            self._save()

    def list_repositories(self) -> List[RepositoryRecord]:
        """Returns all registered repositories, refreshing from disk first."""
        self._load()
        return list(self._repositories.values())

    def get_repository(self, repo_id_or_graph: str) -> Optional[RepositoryRecord]:
        """Looks up a repository by ID, graph name, or path/URL, reloading on cache miss."""
        # 1. Direct ID match in memory
        if repo_id_or_graph in self._repositories:
            return self._repositories[repo_id_or_graph]

        # 2. Match by graph name in memory
        for r in self._repositories.values():
            if r.graph_name == repo_id_or_graph:
                return r

        # 3. Match by path or url in memory
        for r in self._repositories.values():
            if r.url_or_path.lower() == repo_id_or_graph.strip().lower():
                return r

        # Cache miss: reload from disk in case another process/worker registered it
        self._load()

        if repo_id_or_graph in self._repositories:
            return self._repositories[repo_id_or_graph]

        for r in self._repositories.values():
            if r.graph_name == repo_id_or_graph:
                return r

        for r in self._repositories.values():
            if r.url_or_path.lower() == repo_id_or_graph.strip().lower():
                return r

        return None

    def register_local_repository(
        self,
        local_path: str,
        display_name: Optional[str] = None,
        custom_graph_name: Optional[str] = None,
    ) -> RepositoryRecord:
        """Registers a local repository folder."""
        p = Path(local_path).resolve()
        if not p.exists() or not p.is_dir():
            raise ValueError(f"Directory path '{local_path}' does not exist or is not a directory.")

        name = display_name or p.name
        slug = re.sub(r"[^A-Za-z0-9_]", "_", p.name.lower())
        repo_id = f"repo:local_{slug}"
        graph_name = custom_graph_name or sanitize_graph_name(slug)

        record = RepositoryRecord(
            id=repo_id,
            name=name,
            source_type=SourceType.LOCAL,
            url_or_path=str(p),
            graph_name=graph_name,
            status="REGISTERED",
            capabilities=[
                SourceCapability(
                    source_id="src:local_git",
                    source_type=SourceType.LOCAL,
                    repository_identifier=repo_id,
                    data_categories=["code_ast", "git_history"],
                    status=CollectionStatus.PENDING,
                )
            ],
        )
        self._repositories[repo_id] = record
        self._save()
        return record

    def register_github_repository(
        self,
        github_url: str,
        display_name: Optional[str] = None,
        custom_graph_name: Optional[str] = None,
    ) -> RepositoryRecord:
        """Validates and registers a public GitHub repository."""
        validated_url = PublicGitHubUrl.parse_and_validate(github_url)
        repo_id = f"repo:{validated_url.owner.lower()}_{validated_url.repo.lower()}"
        graph_name = custom_graph_name or sanitize_graph_name(f"{validated_url.owner}_{validated_url.repo}")

        name = display_name or f"{validated_url.owner}/{validated_url.repo}"

        record = RepositoryRecord(
            id=repo_id,
            name=name,
            owner=validated_url.owner,
            repo=validated_url.repo,
            source_type=SourceType.GITHUB,
            url_or_path=validated_url.canonical_url,
            graph_name=graph_name,
            status="REGISTERED",
            capabilities=[
                SourceCapability(
                    source_id="src:github_clone",
                    source_type=SourceType.GITHUB,
                    repository_identifier=repo_id,
                    data_categories=["code_ast", "git_history"],
                    status=CollectionStatus.PENDING,
                ),
                SourceCapability(
                    source_id="src:github_api",
                    source_type=SourceType.GITHUB,
                    repository_identifier=repo_id,
                    data_categories=["public_pull_requests", "review_events"],
                    status=CollectionStatus.PENDING,
                ),
            ],
        )
        self._repositories[repo_id] = record
        self._save()
        return record

    def register_archive_repository(
        self,
        extracted_path: str,
        archive_name: str,
        display_name: Optional[str] = None,
        custom_graph_name: Optional[str] = None,
    ) -> RepositoryRecord:
        """Registers an uploaded repository ZIP archive extraction."""
        p = Path(extracted_path).resolve()
        name = display_name or archive_name
        slug = re.sub(r"[^A-Za-z0-9_]", "_", archive_name.lower()).strip("_")
        if not slug:
            slug = "archive"
        repo_id = f"repo:archive_{slug}"
        graph_name = custom_graph_name or sanitize_graph_name(f"archive_{slug}")

        has_git = (p / ".git").is_dir()
        known_gaps = (
            [] if has_git else ["Commit and reviewer history unavailable (uploaded archive lacks .git metadata)"]
        )

        record = RepositoryRecord(
            id=repo_id,
            name=name,
            source_type=SourceType.ARCHIVE,
            url_or_path=str(p),
            graph_name=graph_name,
            status="REGISTERED",
            capabilities=[
                SourceCapability(
                    source_id="src:archive_zip",
                    source_type=SourceType.ARCHIVE,
                    repository_identifier=repo_id,
                    data_categories=["code_ast"] + (["git_history"] if has_git else []),
                    status=CollectionStatus.COLLECTED if has_git else CollectionStatus.PARTIAL,
                    known_gaps=known_gaps,
                )
            ],
            known_gaps=known_gaps,
        )
        self._repositories[repo_id] = record
        self._save()
        return record

    def update_repository(self, record: RepositoryRecord) -> None:
        """Updates and persists repository metadata."""
        self._repositories[record.id] = record
        self._save()


# Singleton registry instance
repo_registry = RepositoryRegistry()
