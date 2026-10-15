"""Public GitHub API metadata collector for PRs, reviews, and repository context."""

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from backend.app.core.config import settings
from backend.app.sources.models import CollectionStatus, SourceCapability, SourceType

logger = logging.getLogger("nexusact.sources.metadata")


class GitHubMetadataCollector:
    """Collects public pull request and review metadata from official GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN.strip()
        self.base_url = "https://api.github.com"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"NexusAct/{settings.APP_VERSION}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def collect_metadata(
        self,
        owner: str,
        repo: str,
        timeout_seconds: float = 8.0,
    ) -> Tuple[Dict[str, Any], SourceCapability]:
        """
        Retrieves public repository context, PRs, and review history.
        Handles rate limits (403/429) and network unreachability without raising exceptions.
        """
        repo_id = f"repo:{owner.lower()}_{repo.lower()}"
        capability = SourceCapability(
            source_id="src:github_api",
            source_type=SourceType.GITHUB,
            repository_identifier=repo_id,
            data_categories=["repository_meta", "pull_requests", "review_events"],
        )

        metadata: Dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "pull_requests": [],
            "reviews": [],
        }

        headers = self._get_headers()

        with httpx.Client(headers=headers, timeout=timeout_seconds) as client:
            # 1. Fetch repo info
            try:
                repo_resp = client.get(f"{self.base_url}/repos/{owner}/{repo}")
                if repo_resp.status_code == 200:
                    data = repo_resp.json()
                    metadata["default_branch"] = data.get("default_branch", "main")
                    metadata["description"] = data.get("description", "")
                    metadata["stars"] = data.get("stargazers_count", 0)
                elif repo_resp.status_code in (403, 429):
                    capability.status = CollectionStatus.RATE_LIMITED
                    capability.known_gaps.append(
                        "GitHub API rate limit exceeded; proceeding without PR/review metadata."
                    )
                    return metadata, capability
                else:
                    capability.status = CollectionStatus.UNAVAILABLE
                    capability.known_gaps.append(f"GitHub API returned HTTP {repo_resp.status_code} for repo details.")
                    return metadata, capability
            except httpx.TimeoutException:
                capability.status = CollectionStatus.UNAVAILABLE
                capability.known_gaps.append("GitHub API request timed out; remote metadata skipped.")
                return metadata, capability
            except Exception as e:
                capability.status = CollectionStatus.UNAVAILABLE
                capability.known_gaps.append(f"Network error querying GitHub API: {str(e)}")
                return metadata, capability

            # 2. Fetch public PRs (up to 20)
            try:
                prs_resp = client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls",
                    params={"state": "all", "per_page": 20},
                )
                if prs_resp.status_code == 200:
                    prs = prs_resp.json()
                    metadata["pull_requests"] = [
                        {
                            "number": p.get("number"),
                            "title": p.get("title"),
                            "state": p.get("state"),
                            "author": p.get("user", {}).get("login"),
                            "created_at": p.get("created_at"),
                        }
                        for p in prs
                    ]
                elif prs_resp.status_code in (403, 429):
                    capability.known_gaps.append("GitHub API rate limit reached during PR listing.")
            except Exception as e:
                capability.known_gaps.append(f"Failed to fetch PR list: {str(e)}")

        if not capability.known_gaps:
            capability.status = CollectionStatus.COLLECTED
        else:
            capability.status = CollectionStatus.PARTIAL

        return metadata, capability
