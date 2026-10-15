"""Local Git commit history extractor for developer attribution and file modifications."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class GitCommitInfo(BaseModel):
    """Extracted Git commit record."""

    hash: str = Field(..., description="Commit full or abbreviated SHA")
    timestamp: str = Field(..., description="ISO 8601 commit timestamp")
    author_name: str = Field(..., description="Commit author name")
    author_email: str = Field(..., description="Normalized commit author email")
    message: str = Field(..., description="First line of commit message")
    files_touched: List[str] = Field(default_factory=list, description="Relative paths of modified files")


class GitHistoryExtractor:
    """Extracts commit logs and author provenance directly from a local git repository."""

    def __init__(self, repo_path: str, max_commits: int = 100):
        self.repo_path = Path(repo_path).resolve()
        self.max_commits = max_commits

    def is_git_repository(self) -> bool:
        """Verifies if the specified path is inside a working Git repository."""
        git_dir = self.repo_path / ".git"
        return git_dir.exists()

    def get_current_head_sha(self) -> str:
        """Returns the current HEAD commit hash."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "unknown_revision"

    def extract_commits(self) -> List[GitCommitInfo]:
        """Extracts the commit history and files touched using git log."""
        if not self.is_git_repository():
            return []

        # Separator to parse commit fields safely
        delimiter = "<|GAF_DELIM|>"
        # Format: hash | author_name | author_email | iso_date | subject
        cmd = [
            "git",
            "log",
            f"-n{self.max_commits}",
            f"--pretty=format:{delimiter}%H{delimiter}%an{delimiter}%ae{delimiter}%aI{delimiter}%s",
            "--name-only",
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return []

        commits: List[GitCommitInfo] = []
        raw_output = proc.stdout.strip()
        if not raw_output:
            return []

        blocks = raw_output.split(delimiter)[1:]  # First element is empty before delimiter
        for i in range(0, len(blocks), 5):
            if i + 4 >= len(blocks):
                break
            sha = blocks[i].strip()
            name = blocks[i + 1].strip()
            email = blocks[i + 2].strip().lower()
            date_str = blocks[i + 3].strip()

            # The 5th item contains the commit subject and any file names before the next block
            fifth_part = blocks[i + 4]
            lines = [line.strip() for line in fifth_part.splitlines() if line.strip()]
            subject = lines[0] if lines else "Commit"
            files_touched = lines[1:] if len(lines) > 1 else []

            # Normalize file paths to forward slashes
            normalized_files = [f.replace("\\", "/") for f in files_touched]

            commits.append(
                GitCommitInfo(
                    hash=sha,
                    timestamp=date_str or datetime.now(timezone.utc).isoformat(),
                    author_name=name or "Unknown Author",
                    author_email=email or "unknown@local.git",
                    message=subject,
                    files_touched=normalized_files,
                )
            )

        return commits
