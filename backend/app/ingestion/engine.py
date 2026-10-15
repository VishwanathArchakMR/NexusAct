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

    repository_path: str
    repository_name: str
    commit_sha: str
    file_count: int
    module_count: int
    import_edge_count: int
    commit_count: int
    contributor_count: int
    resolved_imports_count: int
    unresolved_imports_count: int
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
    ) -> IngestionReport:
        target_path = Path(repo_path or settings.NEXUSACT_REPOSITORY_PATH).resolve()

        target_graph = graph_name or self.client.primary_graph_name

        logger.info("Starting ingestion of [%s] into graph [%s]", target_path, target_graph)

        # 1. Parse AST
        ast_parser = RepositoryAstParser(str(target_path))
        ast_parser.parse_all()

        # 2. Extract Git History
        git_extractor = GitHistoryExtractor(str(target_path))
        commits = git_extractor.extract_commits()
        commit_sha = git_extractor.get_current_head_sha()

        repo_name = target_path.name
        now_iso = datetime.now(timezone.utc).isoformat()

        # 3. Create or Merge Repository Node
        repo_query = """
        MERGE (r:Repository {id: $repo_id})
        SET r.name = $name,
            r.path = $path,
            r.commit_sha = $sha,
            r.last_ingested_at = $ingested_at
        RETURN r.id
        """
        self.client.query(
            repo_query,
            params={
                "repo_id": f"repo:{repo_name}",
                "name": repo_name,
                "path": str(target_path),
                "sha": commit_sha,
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
                params={"repo_id": f"repo:{repo_name}", "mod_id": mod_id},
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

        report = IngestionReport(
            repository_path=str(target_path),
            repository_name=repo_name,
            commit_sha=commit_sha,
            file_count=len(ast_parser.file_map),
            module_count=len(ast_parser.module_map),
            import_edge_count=import_edges_count,
            commit_count=len(commits),
            contributor_count=len(contributors_set),
            resolved_imports_count=resolved_count,
            unresolved_imports_count=unresolved_count,
            ingested_at=now_iso,
        )

        logger.info("Ingestion completed: %s", report.model_dump())
        return report


# Global engine instance
ingestion_engine = RepositoryIngestionEngine()
