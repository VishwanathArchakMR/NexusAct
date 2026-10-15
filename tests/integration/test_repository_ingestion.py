"""Deterministic evaluation tests for Repository Ingestion and AST Parsing.

Covers Section 11 Requirements:
1. Repository ingestion is repeatable and does not duplicate stable entities or relationships.
2. Python relative imports are resolved correctly where possible.
3. Unresolved and dynamic imports are not invented as confirmed dependencies.
"""

import tempfile
from pathlib import Path

from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.ingestion.ast_parser import RepositoryAstParser
from backend.app.ingestion.engine import RepositoryIngestionEngine


def test_relative_import_resolution():
    """Verify that Python relative imports are resolved correctly to internal modules."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        pkg = root / "mypackage"
        sub = pkg / "subpkg"
        sub.mkdir(parents=True)

        (pkg / "__init__.py").write_text("# root pkg", encoding="utf-8")
        (sub / "__init__.py").write_text("# sub pkg", encoding="utf-8")
        (sub / "service.py").write_text("class Service:\n    pass\n", encoding="utf-8")
        (sub / "consumer.py").write_text("from .service import Service\nfrom .. import __version__\n", encoding="utf-8")

        parser = RepositoryAstParser(str(root))
        files = parser.discover_files()
        assert len(files) == 4

        parser.parse_all()
        consumer_meta = next(f for f in parser.file_map.values() if f.relative_path.endswith("consumer.py"))

        resolved_mods = [e.target_module for e in consumer_meta.imports if e.is_resolved]
        assert "mypackage.subpkg.service" in resolved_mods
        assert "mypackage" in resolved_mods


def test_unresolved_and_dynamic_imports_are_not_invented():
    """Verify that unresolved and dynamic imports are not recorded as confirmed internal dependencies."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "script.py").write_text(
            "import os\n"
            "import sys\n"
            "import nonexistent_package_xyz\n"
            "import importlib\n"
            "mod = importlib.import_module('dynamic_lib')\n",
            encoding="utf-8",
        )

        parser = RepositoryAstParser(str(root))
        parser.parse_all()
        meta = list(parser.file_map.values())[0]

        # External and unresolved imports must have is_resolved=False
        unresolved = [e for e in meta.imports if not e.is_resolved]
        unresolved_names = [e.imported_name for e in unresolved]

        assert "nonexistent_package_xyz" in unresolved_names
        assert "os" in unresolved_names
        assert "sys" in unresolved_names

        # None of the unresolved imports should resolve to internal IDs
        assert all(e.target_module is None for e in unresolved)


def test_ingestion_repeatability_and_idempotency():
    """Verify that repeated ingestion does not duplicate nodes or relationships in FalkorDB."""
    test_graph = "test_ingest_idempotency"
    try:
        engine = RepositoryIngestionEngine(graph_client)

        # Ingest local repo into isolated test graph
        report1 = engine.ingest(repo_path=".", graph_name=test_graph)
        assert report1.module_count > 0
        assert report1.import_edge_count > 0

        # Query counts after 1st run
        node_res1 = graph_client.query(f"MATCH (n:{LABEL_MODULE}) RETURN count(n)", graph_name=test_graph)
        edge_res1 = graph_client.query(f"MATCH ()-[r:{REL_DEPENDS_ON}]->() RETURN count(r)", graph_name=test_graph)
        nodes_after_first = node_res1[0][0]
        edges_after_first = edge_res1[0][0]

        # Re-run ingestion
        report2 = engine.ingest(repo_path=".", graph_name=test_graph)
        assert report2.status == "COMPLETED"

        # Query counts after 2nd run
        node_res2 = graph_client.query(f"MATCH (n:{LABEL_MODULE}) RETURN count(n)", graph_name=test_graph)
        edge_res2 = graph_client.query(f"MATCH ()-[r:{REL_DEPENDS_ON}]->() RETURN count(r)", graph_name=test_graph)
        nodes_after_second = node_res2[0][0]
        edges_after_second = edge_res2[0][0]

        assert nodes_after_first == nodes_after_second, "Node count duplicated on re-ingestion!"
        assert edges_after_first == edges_after_second, "Edge count duplicated on re-ingestion!"
    finally:
        graph_client.delete_graph(test_graph)
