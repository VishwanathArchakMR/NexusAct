"""Repository Ingestion Engine orchestrating AST extraction and FalkorDB graph persistence."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import (
    format_file_id,
    format_module_id,
    format_person_id,
)
from backend.app.ingestion.ast_parser import RepositoryAstParser
from backend.app.ingestion.git_history import GitHistoryExtractor

logger = logging.getLogger("nexusact.ingestion.engine")


class IngestionReport(BaseModel):
    """Detailed summary of repository graph ingestion."""

    repository_id: str = "repo:local"
    repository_path: str
    repository_name: str
    graph_name: str = "nexusact_main"
    commit_sha: str
    file_count: int
    module_count: int
    import_edge_count: int
    commit_count: int
    contributor_count: int
    resolved_imports_count: int
    unresolved_imports_count: int
    skipped_files_count: int = 0
    pull_request_count: int = 0
    parser_warnings: list[str] = []
    data_gaps: list[str] = []
    ingested_at: str
    status: str = "COMPLETED"


class RepositoryIngestionEngine:
    """Manages the full pipeline of extracting code structure and storing it in FalkorDB."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or graph_client

    def ingest(
        self,
        repo_path: Optional[str] = None,
        graph_name: Optional[str] = None,
        repo_id: Optional[str] = None,
        github_metadata: Optional[dict] = None,
    ) -> IngestionReport:
        from backend.app.graph.initialization import initialize_schema
        from backend.app.sources.registry import repo_registry

        target_path = Path(repo_path or settings.NEXUSACT_REPOSITORY_PATH).resolve()
        target_graph = graph_name or self.client.primary_graph_name

        logger.info("Starting ingestion of [%s] into graph [%s]", target_path, target_graph)

        # 0. Initialize schema on target graph if needed
        try:
            initialize_schema(self.client, graph_name=target_graph)
        except Exception as exc:
            logger.warning("Schema initialization warning on %s: %s", target_graph, exc)

        # 1. Parse AST
        ast_parser = RepositoryAstParser(str(target_path))
        ast_parser.parse_all()

        # 2. Extract Git History
        git_extractor = GitHistoryExtractor(str(target_path))
        commits = git_extractor.extract_commits()
        commit_sha = git_extractor.get_current_head_sha()

        repo_name = target_path.name
        now_iso = datetime.now(timezone.utc).isoformat()
        resolved_repo_id = repo_id or f"repo:{repo_name}"

        # 3. Create or Merge Repository Node
        repo_query = """
        MERGE (r:Repository {id: $repo_id})
        SET r.name = $name,
            r.path = $path,
            r.commit_sha = $sha,
            r.graph_name = $graph,
            r.last_ingested_at = $ingested_at
        RETURN r.id
        """
        self.client.query(
            repo_query,
            params={
                "repo_id": resolved_repo_id,
                "name": repo_name,
                "path": str(target_path),
                "sha": commit_sha,
                "graph": target_graph,
                "ingested_at": now_iso,
            },
            graph_name=target_graph,
        )

        # 4. Ingest Modules & Files Idempotently
        for mod_name, mod_info in ast_parser.module_map.items():
            mod_id = format_module_id(mod_name)
            # Merge Module
            self.client.query(
                """
                MERGE (m:Module {id: $id})
                SET m.name = $name, m.path = $path
                """,
                params={"id": mod_id, "name": mod_name, "path": mod_info.path},
                graph_name=target_graph,
            )
            # Link Repository -> Module
            self.client.query(
                """
                MATCH (r:Repository {id: $repo_id}), (m:Module {id: $mod_id})
                MERGE (r)-[:CONTAINS]->(m)
                """,
                params={"repo_id": resolved_repo_id, "mod_id": mod_id},
                graph_name=target_graph,
            )

            # Ingest and link files
            for file_path in mod_info.files:
                file_id = format_file_id(file_path)
                file_info = ast_parser.file_map.get(file_path)
                size_bytes = file_info.size_bytes if file_info else 0

                self.client.query(
                    """
                    MERGE (f:File {id: $id})
                    SET f.path = $path, f.size_bytes = $size
                    """,
                    params={"id": file_id, "path": file_path, "size": size_bytes},
                    graph_name=target_graph,
                )
                self.client.query(
                    """
                    MATCH (m:Module {id: $mod_id}), (f:File {id: $file_id})
                    MERGE (m)-[:CONTAINS]->(f)
                    """,
                    params={"mod_id": mod_id, "file_id": file_id},
                    graph_name=target_graph,
                )

        # 5. Ingest Module Dependencies (Canonical: DependentModule -> DEPENDS_ON -> DependencyModule)
        import_edges_count = 0
        resolved_count = 0
        unresolved_count = 0

        for rel_path, file_info in ast_parser.file_map.items():
            for imp in file_info.imports:
                if imp.is_resolved and imp.target_module and imp.target_module != file_info.module_name:
                    resolved_count += 1
                    src_mod_id = format_module_id(file_info.module_name)
                    tgt_mod_id = format_module_id(imp.target_module)

                    # Create canonical dependency edge
                    dep_query = """
                    MATCH (src:Module {id: $src_id}), (tgt:Module {id: $tgt_id})
                    MERGE (src)-[r:DEPENDS_ON {source_file: $src_file}]->(tgt)
                    ON CREATE SET r.evidence = 'observed', r.created_at = $ts
                    ON MATCH SET r.updated_at = $ts
                    """
                    self.client.query(
                        dep_query,
                        params={
                            "src_id": src_mod_id,
                            "tgt_id": tgt_mod_id,
                            "src_file": rel_path,
                            "ts": now_iso,
                        },
                        graph_name=target_graph,
                    )
                    import_edges_count += 1
                else:
                    unresolved_count += 1

        # 6. Ingest Contributors and Commits
        contributors_set = set()
        for c in commits:
            person_id = format_person_id(c.author_email)
            contributors_set.add(person_id)
            commit_id = f"commit:{c.hash}"

            # Merge Person
            self.client.query(
                """
                MERGE (p:Person {id: $id})
                SET p.name = $name, p.email = $email
                """,
                params={"id": person_id, "name": c.author_name, "email": c.author_email},
                graph_name=target_graph,
            )

            # Merge Commit
            self.client.query(
                """
                MERGE (cm:Commit {id: $id})
                SET cm.hash = $hash, cm.timestamp = $ts, cm.message = $msg
                """,
                params={"id": commit_id, "hash": c.hash, "ts": c.timestamp, "msg": c.message},
                graph_name=target_graph,
            )

            # Person -[:AUTHORED]-> Commit
            self.client.query(
                """
                MATCH (p:Person {id: $pid}), (cm:Commit {id: $cid})
                MERGE (p)-[:AUTHORED]->(cm)
                """,
                params={"pid": person_id, "cid": commit_id},
                graph_name=target_graph,
            )

            # Commit -[:TOUCHES]-> File
            for touched_file in c.files_touched:
                f_id = format_file_id(touched_file)
                self.client.query(
                    """
                    MATCH (cm:Commit {id: $cid}), (f:File {id: $fid})
                    MERGE (cm)-[:TOUCHES]->(f)
                    """,
                    params={"cid": commit_id, "fid": f_id},
                    graph_name=target_graph,
                )

        # 7. Ingest Public Pull Requests & Reviews (if available from GitHub metadata)
        pr_count = 0
        data_gaps: list[str] = []
        if github_metadata and "pull_requests" in github_metadata:
            for pr in github_metadata["pull_requests"]:
                pr_num = pr.get("number")
                if pr_num is not None:
                    pr_count += 1
                    pr_id = f"pr:{repo_name}:{pr_num}"
                    self.client.query(
                        """
                        MERGE (pr:PullRequest {id: $id})
                        SET pr.number = $num, pr.title = $title, pr.state = $state, pr.author = $author
                        """,
                        params={
                            "id": pr_id,
                            "num": pr_num,
                            "title": pr.get("title") or "",
                            "state": pr.get("state") or "",
                            "author": pr.get("author") or "",
                        },
                        graph_name=target_graph,
                    )
        else:
            data_gaps.append("PR peer review records unavailable in local Git history")

        if not ast_parser.module_map:
            data_gaps.append(
                "No supported Python source files (.py) found in repository. "
                "TypeScript, JavaScript, and non-Python source files are not "
                "currently parsed into code dependency modules."
            )

        if ast_parser.skipped_files:
            data_gaps.append(f"{len(ast_parser.skipped_files)} file(s) skipped due to syntax or encoding errors")

        report = IngestionReport(
            repository_id=resolved_repo_id,
            repository_path=str(target_path),
            repository_name=repo_name,
            graph_name=target_graph,
            commit_sha=commit_sha,
            file_count=len(ast_parser.file_map),
            module_count=len(ast_parser.module_map),
            import_edge_count=import_edges_count,
            commit_count=len(commits),
            contributor_count=len(contributors_set),
            resolved_imports_count=resolved_count,
            unresolved_imports_count=unresolved_count,
            skipped_files_count=len(ast_parser.skipped_files),
            pull_request_count=pr_count,
            parser_warnings=ast_parser.parser_warnings[:20],
            data_gaps=data_gaps,
            ingested_at=now_iso,
        )

        # 8. Synchronize repository registry record
        repo_rec = repo_registry.get_repository(resolved_repo_id) or repo_registry.get_repository(target_graph)
        if repo_rec:
            repo_rec.commit_sha = commit_sha
            repo_rec.file_count = report.file_count
            repo_rec.module_count = report.module_count
            repo_rec.edge_count = report.import_edge_count
            repo_rec.commit_count = report.commit_count
            repo_rec.contributor_count = report.contributor_count
            repo_rec.last_ingested_at = now_iso
            repo_rec.status = "INGESTED"
            repo_rec.known_gaps = data_gaps
            repo_rec.parser_warnings = ast_parser.parser_warnings[:20]
            repo_registry.update_repository(repo_rec)

        logger.info("Ingestion completed: %s", report.model_dump())
        return report


# Global engine instance
ingestion_engine = RepositoryIngestionEngine()
