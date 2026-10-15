"""Bounded, secure GitHub repository cloner and revision fetcher."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from backend.app.sources.models import PublicGitHubUrl
from backend.app.sources.registry import get_cache_root

logger = logging.getLogger("nexusact.sources.fetcher")


class GitHubRepoFetcher:
    """Safely clones and updates public GitHub repositories outside the application source tree."""

    def __init__(self, cache_root: Optional[Path] = None):
        self.repos_dir = (cache_root or get_cache_root()) / "repos"
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_cache_dir(self, owner: str, repo: str) -> Path:
        """Returns the isolated disk directory for a repository."""
        return self.repos_dir / f"{owner.lower()}_{repo.lower()}"

    def clone_or_update(
        self,
        validated_url: PublicGitHubUrl,
        depth: int = 50,
        timeout_seconds: int = 120,
    ) -> Tuple[Path, str]:
        """
        Safely fetches or clones the permitted public GitHub repository into cache.
        Returns:
            (checkout_path, commit_sha)
        Safety controls:
        - Strict HTTPS URL validation before execution.
        - Dedicated local cache outside application source tree.
        - Subprocess invocation using argument vector (NEVER shell string interpolation).
        - Explicit depth bounds and timeouts.
        - Pure metadata/source fetch; NO build scripts or commands are executed.
        """
        checkout_dir = self.get_repo_cache_dir(validated_url.owner, validated_url.repo)

        if checkout_dir.exists() and (checkout_dir / ".git").is_dir():
            logger.info("Found existing checkout at %s. Fetching latest revision...", checkout_dir)
            try:
                # Bounded fetch
                cmd = ["git", "fetch", "--depth", str(depth), "origin"]
                subprocess.run(
                    cmd,
                    cwd=str(checkout_dir),
                    check=True,
                    timeout=timeout_seconds,
                    capture_output=True,
                    text=True,
                )
            except subprocess.TimeoutExpired as te:
                raise TimeoutError(
                    f"Git fetch timed out after {timeout_seconds}s for {validated_url.canonical_url}"
                ) from te
            except Exception as e:
                logger.warning("Git fetch failed; using existing cache: %s", e)
        else:
            logger.info(
                "Cloning public repository %s into %s (depth=%d)...", validated_url.canonical_url, checkout_dir, depth
            )
            checkout_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                "git",
                "clone",
                "--depth",
                str(depth),
                "--single-branch",
                validated_url.canonical_url,
                str(checkout_dir),
            ]
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    timeout=timeout_seconds,
                    capture_output=True,
                    text=True,
                )
                logger.info("Clone completed: %s", result.stdout)
            except subprocess.TimeoutExpired as te:
                raise TimeoutError(
                    f"Git clone timed out after {timeout_seconds}s for {validated_url.canonical_url}"
                ) from te
            except subprocess.CalledProcessError as cpe:
                err_msg = cpe.stderr.strip() or cpe.stdout.strip()
                raise RuntimeError(f"Git clone failed for {validated_url.canonical_url}: {err_msg}") from cpe

        # Read exact HEAD commit SHA
        sha = self.get_head_sha(checkout_dir)
        return checkout_dir, sha

    def get_head_sha(self, checkout_dir: Path) -> str:
        """Reads the exact current commit SHA."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(checkout_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return res.stdout.strip()
        except Exception as e:
            logger.warning("Failed to determine HEAD SHA via git: %s", e)
            return "UNKNOWN"
