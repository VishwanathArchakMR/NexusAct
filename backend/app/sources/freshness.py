"""Source freshness verification, fingerprinting, and snapshot lifecycle management."""

import hashlib
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set, Tuple

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE
from backend.app.ingestion.engine import RepositoryIngestionEngine
from backend.app.sources.github_fetcher import GitHubRepoFetcher
from backend.app.sources.github_metadata import GitHubMetadataCollector
from backend.app.sources.models import (
    PublicGitHubUrl,
    SourceSnapshot,
    SourceType,
)
from backend.app.sources.registry import repo_registry

logger = logging.getLogger("nexusact.sources.freshness")

# File extensions tracked for local source freshness
RELEVANT_EXTENSIONS: Set[str] = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

# Directories ignored during fingerprinting
EXCLUDED_DIRS: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".cache",
    "coverage",
    "logs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
}


def compute_working_tree_fingerprint(repo_path: Path) -> Tuple[str, str]:
    """
    Computes a deterministic fingerprint of relevant source files in the local working tree,
    plus the current git commit SHA.

    Returns:
        (commit_sha, fingerprint_hash)
    """
    commit_sha = "HEAD"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        commit_sha = res.stdout.strip()
    except Exception as e:
        logger.debug("Failed reading git HEAD in %s: %s", repo_path, e)

    h = hashlib.sha256()
    h.update(commit_sha.encode("utf-8"))

    # Walk relevant files in deterministic sorted order
    file_entries = []
    try:
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                if p.suffix.lower() in RELEVANT_EXTENSIONS:
                    try:
                        stat = p.stat()
                        rel_path = p.relative_to(repo_path).as_posix()
                        file_entries.append((rel_path, int(stat.st_mtime), stat.st_size))
                    except Exception:
                        pass
    except Exception as e:
        logger.warning("Error walking repository directory %s: %s", repo_path, e)

    file_entries.sort(key=lambda x: x[0])
    for rel_path, mtime, size in file_entries:
        h.update(f"{rel_path}:{mtime}:{size}\n".encode("utf-8"))

    fingerprint = h.hexdigest()[:16]
    return commit_sha, fingerprint


def query_remote_github_head(canonical_url: str, timeout_sec: int = 8) -> Optional[str]:
    """
    Queries the current upstream default branch commit SHA for a public GitHub repository
    using git ls-remote without cloning.
    """
    try:
        cmd = ["git", "ls-remote", canonical_url, "HEAD"]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=True,
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "HEAD":
                return parts[0]
        return None
    except Exception as e:
        logger.warning("git ls-remote failed for %s: %s", canonical_url, e)
        return None


class SourceFreshnessService:
    """Ensures source freshness and manages verified snapshots before investigations."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or graph_client
        self.engine = RepositoryIngestionEngine(self.client)
        self.fetcher = GitHubRepoFetcher()

    def check_and_refresh_source(
        self,
        repo_id: str,
        force_refresh: bool = False,
    ) -> SourceSnapshot:
        """
        Authoritatively establishes the freshness of the selected repository.

        Behavior:
        1. For Local Repositories:
           - Resolves Git HEAD and computes working-tree fingerprint.
           - If fingerprint unchanged and graph contains parsed modules: returns FRESH snapshot.
           - If changed or graph empty or force_refresh: ingests working tree into FalkorDB,
             validates the graph, updates registry, and returns UPDATED snapshot.
        2. For GitHub Repositories:
           - Queries upstream default-branch commit SHA via git ls-remote.
           - If remote commit matches indexed commit and graph healthy: returns FRESH snapshot.
           - If remote commit differs or graph empty: fetches revision, ingests into FalkorDB,
             validates graph, updates registry, and returns UPDATED snapshot.
           - If remote check fails: marks STALE_SOURCE_UNAVAILABLE while preserving last known-good snapshot.
        """
        record = repo_registry.get_repository(repo_id)
        if not record:
            raise ValueError(f"Repository '{repo_id}' is not registered.")

        now_iso = datetime.now(timezone.utc).isoformat()
        record.source_checked_at = now_iso

        # Verify existing graph health
        graph_healthy = False
        try:
            cnt = self.client.query(
                f"MATCH (m:{LABEL_MODULE}) RETURN count(m)",
                graph_name=record.graph_name,
            )[0][0]
            graph_healthy = cnt > 0
        except Exception:
            graph_healthy = False

        # --- LOCAL REPOSITORY FRESHNESS ---
        if record.source_type == SourceType.LOCAL:
            local_path = Path(record.url_or_path).resolve()
            if not local_path.exists():
                record.freshness_status = "STALE_SOURCE_UNAVAILABLE"
                repo_registry.update_repository(record)
                return record.to_snapshot()

            commit_sha, current_fp = compute_working_tree_fingerprint(local_path)
            record.commit_sha = commit_sha

            needs_reingestion = (
                force_refresh
                or not graph_healthy
                or record.working_tree_fingerprint != current_fp
                or record.status != "INGESTED"
            )

            if not needs_reingestion:
                record.freshness_status = "FRESH"
                repo_registry.update_repository(record)
                return record.to_snapshot()

            logger.info(
                "Local repository %s source changed (fp: %s -> %s) or needs refresh. Ingesting...",
                record.id,
                record.working_tree_fingerprint,
                current_fp,
            )
            try:
                report = self.engine.ingest(
                    repo_path=str(local_path),
                    graph_name=record.graph_name,
                    repo_id=record.id,
                )
                record.working_tree_fingerprint = current_fp
                record.module_count = report.module_count
                record.edge_count = report.import_edge_count
                record.commit_count = report.commit_count
                record.contributor_count = report.contributor_count
                record.last_ingested_at = report.ingested_at
                record.status = "INGESTED"
                record.freshness_status = "UPDATED"

                # Update active snapshot id
                short_sha = commit_sha[:8]
                short_fp = current_fp[:6]
                slug = record.id.replace("repo:", "")
                record.active_snapshot_id = f"snap_{slug}_{short_sha}_{short_fp}"

                repo_registry.update_repository(record)
                return record.to_snapshot()
            except Exception as e:
                logger.error("Failed to re-ingest local repository %s: %s", record.id, e)
                record.freshness_status = "INGESTION_FAILED"
                repo_registry.update_repository(record)
                return record.to_snapshot()

        # --- GITHUB REPOSITORY FRESHNESS ---
        elif record.source_type == SourceType.GITHUB:
            github_url_str = record.canonical_source or record.url_or_path
            try:
                val_url = PublicGitHubUrl.parse_and_validate(github_url_str)
            except Exception as e:
                logger.error("Invalid GitHub URL for %s: %s", record.id, e)
                record.freshness_status = "SNAPSHOT_UNRESOLVED"
                repo_registry.update_repository(record)
            try:
                remote_sha = query_remote_github_head(val_url.canonical_url)
            except Exception as e:
                logger.warning("Upstream GitHub check failed for %s: %s", record.id, e)
                remote_sha = None

            if not remote_sha:
                # Upstream check failed (offline or rate limited)
                gap_msg = "Remote source unavailable; preserved last verified snapshot."
                if gap_msg not in record.known_gaps:
                    record.known_gaps.append(gap_msg)
                logger.warning(
                    "Upstream GitHub check unreachable for %s. Reusing last verified snapshot as historical.",
                    record.id,
                )
                record.freshness_status = "STALE_SOURCE_UNAVAILABLE"
                repo_registry.update_repository(record)
                return record.to_snapshot()

            needs_update = (
                force_refresh or not graph_healthy or record.commit_sha != remote_sha or record.status != "INGESTED"
            )

            if not needs_update:
                record.freshness_status = "FRESH"
                repo_registry.update_repository(record)
                return record.to_snapshot()

            logger.info(
                "GitHub repository %s has new upstream revision (%s -> %s). Updating checkout and graph...",
                record.id,
                record.commit_sha,
                remote_sha,
            )

            try:
                checkout_path, actual_sha = self.fetcher.clone_or_update(val_url)
                record.commit_sha = actual_sha

                # Collect PR / review metadata
                collector = GitHubMetadataCollector()
                meta, cap = collector.collect_metadata(val_url.owner, val_url.repo)
                record.capabilities = [cap]

                # Ingest into isolated graph
                report = self.engine.ingest(
                    repo_path=str(checkout_path),
                    graph_name=record.graph_name,
                    repo_id=record.id,
                    github_metadata=meta,
                )

                record.module_count = report.module_count
                record.edge_count = report.import_edge_count
                record.commit_count = report.commit_count
                record.contributor_count = report.contributor_count
                record.last_ingested_at = report.ingested_at
                record.status = "INGESTED"
                record.freshness_status = "UPDATED"

                short_sha = actual_sha[:8]
                slug = f"{val_url.owner}_{val_url.repo}"
                record.active_snapshot_id = f"snap_{slug}_{short_sha}"

                repo_registry.update_repository(record)
                return record.to_snapshot()
            except Exception as e:
                logger.error("Failed updating GitHub repository %s: %s", record.id, e)
                record.freshness_status = "INGESTION_FAILED"
                repo_registry.update_repository(record)
                return record.to_snapshot()

        record.freshness_status = "SNAPSHOT_UNRESOLVED"
        return record.to_snapshot()


# Global service instance
source_freshness_service = SourceFreshnessService()
