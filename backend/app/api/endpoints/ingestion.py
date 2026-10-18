"""Repository ingestion and multi-repository management API endpoints."""

import ast
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE
from backend.app.ingestion.engine import IngestionReport, RepositoryIngestionEngine
from backend.app.sources.freshness import source_freshness_service
from backend.app.sources.github_fetcher import GitHubRepoFetcher
from backend.app.sources.github_metadata import GitHubMetadataCollector
from backend.app.sources.models import (
    PublicGitHubUrl,
    RegisterRepositoryRequest,
    RepositoryRecord,
    SourceMetadataOutput,
    SourceSnapshot,
    SourceType,
)
from backend.app.sources.registry import repo_registry

logger = logging.getLogger("nexusact.api.ingestion")
router = APIRouter(prefix="/ingest", tags=["Repository Ingestion"])

# Public judging demo limits: accept public GitHub repositories only, with bounded resource use.
_PUBLIC_GITHUB_REPO_MAX_SIZE_KB = 100_000
_PUBLIC_INGEST_WINDOW_SECONDS = 600.0
_PUBLIC_INGEST_MAX_PER_IP = 8
_PUBLIC_INGEST_LOCK = threading.Lock()
_PUBLIC_INGEST_REQUESTS: Dict[str, List[float]] = {}
_PUBLIC_INGEST_SLOTS = threading.BoundedSemaphore(value=2)


def _public_demo_ingest_guard(request: Request) -> Generator[None, None, None]:
    """Apply a short per-client rate limit and cap concurrent public repository ingestions."""
    if not settings.PUBLIC_DEMO_MODE:
        yield
        return

    # Caddy appends the client address to X-Forwarded-For; the backend is private behind this gateway.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[-1].strip() if forwarded_for else ""
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"

    now = time.monotonic()
    with _PUBLIC_INGEST_LOCK:
        recent = [
            timestamp
            for timestamp in _PUBLIC_INGEST_REQUESTS.get(client_ip, [])
            if now - timestamp < _PUBLIC_INGEST_WINDOW_SECONDS
        ]
        if len(recent) >= _PUBLIC_INGEST_MAX_PER_IP:
            raise HTTPException(
                status_code=429,
                detail="Public repository ingestion rate limit reached. Please wait a few minutes and retry.",
            )
        recent.append(now)
        _PUBLIC_INGEST_REQUESTS[client_ip] = recent

        # Keep the in-memory limiter bounded if the service sees many distinct clients.
        if len(_PUBLIC_INGEST_REQUESTS) > 2048:
            cutoff = now - _PUBLIC_INGEST_WINDOW_SECONDS
            stale_keys = [
                key for key, timestamps in _PUBLIC_INGEST_REQUESTS.items() if not timestamps or max(timestamps) < cutoff
            ]
            for key in stale_keys:
                _PUBLIC_INGEST_REQUESTS.pop(key, None)

    if not _PUBLIC_INGEST_SLOTS.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="The demo is processing other repositories. Please retry in a moment.",
        )
    try:
        yield
    finally:
        _PUBLIC_INGEST_SLOTS.release()


def _check_public_github_repo_size(url: PublicGitHubUrl) -> None:
    """Check GitHub's repository metadata before cloning to reject private/oversized sources."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"NexusAct/{settings.APP_VERSION}",
    }
    if settings.GITHUB_TOKEN.strip():
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN.strip()}"

    try:
        response = httpx.get(
            f"https://api.github.com/repos/{url.owner}/{url.repo}",
            headers=headers,
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Public GitHub repository preflight failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not verify the public GitHub repository. Please retry shortly.",
        ) from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub repository not found or is not public.")
    if response.status_code in (403, 429):
        raise HTTPException(
            status_code=503,
            detail="GitHub API rate limit reached. Please retry in a few minutes.",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub repository preflight returned HTTP {response.status_code}.",
        )

    try:
        size_kb = int(response.json().get("size", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="GitHub returned invalid repository metadata.") from exc

    if size_kb > _PUBLIC_GITHUB_REPO_MAX_SIZE_KB:
        raise HTTPException(
            status_code=413,
            detail="This public demo accepts repositories up to 100 MB. Please try a smaller repository.",
        )


def _validate_public_demo_ingestion_request(payload: "OnboardRepoRequest") -> PublicGitHubUrl:
    """In public demo mode, permit only validated public GitHub URLs or existing GitHub records."""
    if payload.repo_id:
        record = repo_registry.get_repository(payload.repo_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Repository '{payload.repo_id}' not found.")
        if record.source_type != SourceType.GITHUB:
            raise HTTPException(
                status_code=403,
                detail="Public demo mode only permits HTTPS URLs for public GitHub repositories.",
            )
        raw_url = record.canonical_source or record.url_or_path
    elif payload.url_or_path:
        source_type = payload.source_type or (
            SourceType.GITHUB if payload.url_or_path.strip().lower().startswith("https://") else SourceType.LOCAL
        )
        if source_type != SourceType.GITHUB:
            raise HTTPException(
                status_code=403,
                detail="Public demo mode only permits HTTPS URLs for public GitHub repositories.",
            )
        raw_url = payload.url_or_path
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide a public GitHub URL or an existing GitHub repository ID.",
        )

    try:
        validated_url = PublicGitHubUrl.parse_and_validate(raw_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Public demo mode only accepts public GitHub HTTPS URLs: {exc}",
        ) from exc

    _check_public_github_repo_size(validated_url)
    return validated_url


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
    if settings.PUBLIC_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail=(
                "Repository ingestion is disabled in public demo mode. Preloaded graphs are available for exploration."
            ),
        )
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
    if settings.PUBLIC_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail="Repository registration is disabled in public demo mode.",
        )
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


@router.post(
    "/clone-and-ingest",
    response_model=IngestionReport,
    dependencies=[Depends(_public_demo_ingest_guard)],
)
def clone_and_ingest(payload: OnboardRepoRequest) -> IngestionReport:
    """Safely ingests GitHub repositories; public demo mode permits only bounded public HTTPS sources."""
    if settings.PUBLIC_DEMO_MODE:
        _validate_public_demo_ingestion_request(payload)
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
            if settings.PUBLIC_DEMO_MODE:
                # Shallow checkout and strict timeout reduce CPU, disk, and bandwidth use for public visitors.
                checkout_path, commit_sha = fetcher.clone_or_update(val_url, depth=1, timeout_seconds=90)
            else:
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
        working_tree_fingerprint=record.working_tree_fingerprint,
        active_snapshot_id=record.active_snapshot_id,
        freshness_status=record.freshness_status,
        sources=record.capabilities,
        known_gaps=record.known_gaps,
    )


IGNORE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".falkordb",
    "data",
    "htmlcov",
    ".egg-info",
    ".idea",
    ".vscode",
}

LANG_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".toml": "toml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".css": "css",
    ".html": "html",
    ".sh": "bash",
    ".sql": "sql",
    ".txt": "text",
}


class SymbolOutlineItem(BaseModel):
    name: str
    kind: str  # "function" | "class" | "method"
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None


class FileGraphLinkage(BaseModel):
    has_graph_module: bool = False
    module_id: Optional[str] = None
    module_name: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    modeled_level: str = "module_level"


class FileContentResponse(BaseModel):
    file_path: str
    repository_id: str
    commit_sha: str
    start_line: int
    end_line: int
    total_lines: int
    content: str
    language: str
    symbols: List[SymbolOutlineItem] = Field(default_factory=list)
    graph_linkage: Optional[FileGraphLinkage] = None


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    size_bytes: Optional[int] = None
    language: Optional[str] = None
    has_graph_module: bool = False
    module_id: Optional[str] = None
    children: Optional[List["FileTreeNode"]] = None


class FileTreeResponse(BaseModel):
    repository_id: str
    repository_name: str
    commit_sha: str
    total_files: int
    total_directories: int
    tree: List[FileTreeNode]
    truncated: bool = False


@router.get("/snapshot/{repo_id}", response_model=SourceSnapshot)
def get_repository_snapshot(
    repo_id: str,
    refresh: bool = Query(default=False, description="Force freshness verification and update"),
) -> SourceSnapshot:
    """Verifies and returns the authoritative SourceSnapshot for a repository."""
    try:
        return source_freshness_service.check_and_refresh_source(repo_id, force_refresh=refresh)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error("Failed getting snapshot for %s: %s", repo_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file-tree", response_model=FileTreeResponse)
def get_file_tree(
    repo_id: str = Query(..., description="Repository identifier"),
    subpath: Optional[str] = Query(default=None, description="Optional relative directory path"),
    max_depth: int = Query(default=5, ge=1, le=10),
    limit: int = Query(default=800, ge=10, le=3000),
) -> FileTreeResponse:
    """Safely retrieves repository directory hierarchy bounded by depth and entry count."""
    record = repo_registry.get_repository(repo_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    if record.source_type == SourceType.LOCAL:
        base_dir = Path(record.url_or_path).resolve()
    else:
        fetcher = GitHubRepoFetcher()
        raw_url = record.canonical_source or record.url_or_path
        val_url = PublicGitHubUrl.parse_and_validate(raw_url)
        base_dir = fetcher.get_repo_cache_dir(val_url.owner, val_url.repo).resolve()

    if not base_dir.exists():
        raise HTTPException(status_code=404, detail=f"Checkout for repository '{repo_id}' not found on disk.")

    scan_dir = base_dir
    if subpath:
        clean_sub = subpath.replace("\\", "/").lstrip("/")
        target_sub = (base_dir / clean_sub).resolve()
        try:
            target_sub.relative_to(base_dir)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid subpath (escapes repository root).")
        if not target_sub.exists() or not target_sub.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory '{subpath}' not found.")
        scan_dir = target_sub

    # Retrieve graph module map for this repository
    graph_modules: Dict[str, str] = {}
    try:
        rows = graph_client.query(
            "MATCH (m:Module) RETURN m.id, m.name, m.path",
            graph_name=record.graph_name,
        )
        for r in rows:
            m_id, m_name, m_path = r[0], r[1], r[2]
            if m_path:
                norm_p = m_path.replace("\\", "/").lstrip("/")
                graph_modules[norm_p] = m_id
            if m_name:
                graph_modules[m_name] = m_id
    except Exception as e:
        logger.debug("Failed querying module map for %s: %s", repo_id, e)

    file_count = 0
    dir_count = 0
    is_truncated = False

    def scan_level(current_path: Path, current_depth: int) -> List[FileTreeNode]:
        nonlocal file_count, dir_count, is_truncated
        if current_depth > max_depth or is_truncated:
            return []

        try:
            items = list(current_path.iterdir())
        except (PermissionError, OSError):
            return []

        dirs_list = []
        files_list = []

        for item in items:
            name = item.name
            if name.startswith(".") and name not in (".env.example", ".gitignore"):
                continue
            if name in IGNORE_DIRS:
                continue

            try:
                rel = item.relative_to(base_dir).as_posix()
            except ValueError:
                continue

            if item.is_dir():
                dirs_list.append((name, rel, item))
            elif item.is_file():
                files_list.append((name, rel, item))

        dirs_list.sort(key=lambda x: x[0].lower())
        files_list.sort(key=lambda x: x[0].lower())

        entries: List[FileTreeNode] = []

        for d_name, d_rel, d_path in dirs_list:
            dir_count += 1
            children = scan_level(d_path, current_depth + 1)
            entries.append(
                FileTreeNode(
                    name=d_name,
                    path=d_rel,
                    type="directory",
                    children=children,
                )
            )

        for f_name, f_rel, f_path in files_list:
            if file_count >= limit:
                is_truncated = True
                break
            file_count += 1
            try:
                size = f_path.stat().st_size
            except OSError:
                size = 0
            ext = f_path.suffix.lower()
            lang = LANG_MAP.get(ext, "text")
            has_mod = f_rel in graph_modules or f_path.stem in graph_modules
            mod_id = graph_modules.get(f_rel) or graph_modules.get(f_path.stem)

            entries.append(
                FileTreeNode(
                    name=f_name,
                    path=f_rel,
                    type="file",
                    size_bytes=size,
                    language=lang,
                    has_graph_module=has_mod,
                    module_id=mod_id,
                )
            )

        return entries

    tree = scan_level(scan_dir, 1)

    return FileTreeResponse(
        repository_id=record.id,
        repository_name=record.name,
        commit_sha=record.commit_sha,
        total_files=file_count,
        total_directories=dir_count,
        tree=tree,
        truncated=is_truncated,
    )


@router.get("/file-content", response_model=FileContentResponse)
def get_file_content(
    repo_id: str = Query(..., description="Repository identifier"),
    file_path: str = Query(..., description="Relative file path within repository"),
    start_line: int = Query(default=1, ge=1),
    end_line: int = Query(default=200, ge=1),
) -> FileContentResponse:
    """Safely retrieves lines of code from a file in the repository's pinned snapshot
    with symbol outline and graph linkage.
    """
    record = repo_registry.get_repository(repo_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    if record.source_type == SourceType.LOCAL:
        base_dir = Path(record.url_or_path).resolve()
    else:
        fetcher = GitHubRepoFetcher()
        raw_url = record.canonical_source or record.url_or_path
        val_url = PublicGitHubUrl.parse_and_validate(raw_url)
        base_dir = fetcher.get_repo_cache_dir(val_url.owner, val_url.repo).resolve()

    if not base_dir.exists():
        raise HTTPException(status_code=404, detail=f"Checkout for repository '{repo_id}' not found on disk.")

    clean_rel = file_path.replace("\\", "/").lstrip("/")
    target_file = (base_dir / clean_rel).resolve()
    try:
        target_file.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal outside repository root).")

    if not target_file.exists() or not target_file.is_file():
        # Fallback 1: Query FalkorDB to find exact Module or File path in graph
        resolved_path = None
        try:
            m_path_query = """
            MATCH (m:Module)
            WHERE m.id = $p OR m.name = $p OR m.path = $p OR m.id = ('mod:' + $p)
            RETURN m.path LIMIT 1
            """
            rows = graph_client.query(m_path_query, params={"p": clean_rel}, graph_name=record.graph_name)
            if rows and rows[0][0]:
                cand = (base_dir / str(rows[0][0])).resolve()
                if cand.exists() and cand.is_file():
                    target_file = cand
                    resolved_path = str(rows[0][0])
        except Exception:
            pass

        # Fallback 2: Check common programming language extensions if omitted or mismatched
        if not target_file.exists() or not target_file.is_file():
            base_stem = clean_rel.rsplit(".", 1)[0]
            for candidate_ext in [".ts", ".tsx", ".py", ".js", ".jsx", ".json", ".md"]:
                cand = (base_dir / f"{base_stem}{candidate_ext}").resolve()
                if cand.exists() and cand.is_file():
                    target_file = cand
                    resolved_path = f"{base_stem}{candidate_ext}"
                    break

        if not target_file.exists() or not target_file.is_file():
            raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in repository.")

        if resolved_path:
            clean_rel = resolved_path

    try:
        full_text = target_file.read_text(encoding="utf-8", errors="replace")
        lines = full_text.splitlines()
        total_lines = len(lines)
        s_line = max(1, start_line)
        e_line = min(total_lines, max(s_line, end_line))
        slice_lines = lines[s_line - 1 : e_line]
        content = "\n".join(slice_lines)

        ext = target_file.suffix.lower()
        language = LANG_MAP.get(ext, "text")

        # ── Parse symbol outline ─────────────────────────────────────
        symbols: List[SymbolOutlineItem] = []
        if ext == ".py":
            try:
                tree = ast.parse(full_text, filename=clean_rel)
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args_str = ", ".join(a.arg for a in node.args.args[:5])
                        symbols.append(
                            SymbolOutlineItem(
                                name=node.name,
                                kind="function",
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                                signature=f"{node.name}({args_str})",
                                docstring=ast.get_docstring(node),
                            )
                        )
                    elif isinstance(node, ast.ClassDef):
                        symbols.append(
                            SymbolOutlineItem(
                                name=node.name,
                                kind="class",
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                                signature=f"class {node.name}",
                                docstring=ast.get_docstring(node),
                            )
                        )
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                args_str = ", ".join(a.arg for a in item.args.args[:4])
                                symbols.append(
                                    SymbolOutlineItem(
                                        name=f"{node.name}.{item.name}",
                                        kind="method",
                                        start_line=item.lineno,
                                        end_line=getattr(item, "end_lineno", item.lineno),
                                        signature=f"{item.name}({args_str})",
                                        docstring=ast.get_docstring(item),
                                    )
                                )
            except Exception as e:
                logger.debug("AST outline parse error for %s: %s", clean_rel, e)
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            try:
                for line_idx, line in enumerate(lines, 1):
                    fn_match = re.search(r"(?:export\s+)?(?:const|function|async function)\s+([A-Za-z0-9_]+)", line)
                    cls_match = re.search(r"(?:export\s+)?class\s+([A-Za-z0-9_]+)", line)
                    if fn_match:
                        name = fn_match.group(1)
                        if name not in ("if", "for", "switch", "while"):
                            symbols.append(
                                SymbolOutlineItem(
                                    name=name,
                                    kind="function",
                                    start_line=line_idx,
                                    end_line=line_idx,
                                    signature=line.strip()[:60],
                                )
                            )
                    elif cls_match:
                        symbols.append(
                            SymbolOutlineItem(
                                name=cls_match.group(1),
                                kind="class",
                                start_line=line_idx,
                                end_line=line_idx,
                                signature=f"class {cls_match.group(1)}",
                            )
                        )
            except Exception:
                pass

        # ── Link to active FalkorDB graph relationships ───────────────
        graph_link = FileGraphLinkage(has_graph_module=False)
        try:
            m_rows = graph_client.query(
                """
                MATCH (m:Module)
                WHERE m.path = $p OR m.name = $p OR m.name CONTAINS $stem
                RETURN m.id, m.name
                LIMIT 1
                """,
                params={"p": clean_rel, "stem": target_file.stem},
                graph_name=record.graph_name,
            )
            if m_rows:
                mid, mname = m_rows[0][0], m_rows[0][1]
                graph_link.has_graph_module = True
                graph_link.module_id = mid
                graph_link.module_name = mname

                deps_rows = graph_client.query(
                    """
                    MATCH (m:Module)-[:DEPENDS_ON]->(d:Module)
                    WHERE m.id = $mid
                    RETURN d.name, d.id
                    LIMIT 20
                    """,
                    params={"mid": mid},
                    graph_name=record.graph_name,
                )
                graph_link.dependencies = [r[0] or r[1] for r in deps_rows]

                caller_rows = graph_client.query(
                    """
                    MATCH (c:Module)-[:DEPENDS_ON]->(m:Module)
                    WHERE m.id = $mid
                    RETURN c.name, c.id
                    LIMIT 20
                    """,
                    params={"mid": mid},
                    graph_name=record.graph_name,
                )
                graph_link.dependents = [r[0] or r[1] for r in caller_rows]
        except Exception as e:
            logger.debug("Failed querying graph linkage for %s: %s", clean_rel, e)

        return FileContentResponse(
            file_path=clean_rel,
            repository_id=record.id,
            commit_sha=record.commit_sha,
            start_line=s_line,
            end_line=e_line,
            total_lines=total_lines,
            content=content,
            language=language,
            symbols=symbols,
            graph_linkage=graph_link,
        )
    except Exception as e:
        logger.error("Failed reading file %s: %s", target_file, e)
        raise HTTPException(status_code=500, detail=f"Failed reading file content: {str(e)}")


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
