"""Deterministic End-to-End Pipeline & Integration Test Suite.

Validates the complete lifecycle:
1. Real multi-module, multi-contributor repository fixture generation with Git history.
2. Ingestion into an isolated FalkorDB graph and verification of nodes and DEPENDS_ON edges.
3. Natural-language query entity resolution (non-canned question).
4. Reverse dependency impact analysis verifying upstream paths.
5. Contributor knowledge analysis with transparent evidence and no invented conclusions.
6. Counterfactual simulation verifying path breakage while preserving the source graph.
7. Full AdaptiveInvestigationAgent planning and execution loop.
8. Repeated ingestion idempotency.
9. Edge cases: empty repository, syntax error handling, and symlink containment.
"""

import subprocess
import uuid
from pathlib import Path

import pytest

from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.impact import TraceImpactInput, execute_trace_impact
from backend.app.graph.tools.resolve import ResolveEntityInput, execute_resolve_entity
from backend.app.graph.tools.reviewers import WhoKnowsInput, execute_who_knows
from backend.app.graph.tools.simulation import (
    SimulateRemoveModuleInput,
    execute_simulate_remove_module,
)
from backend.app.ingestion.ast_parser import RepositoryAstParser
from backend.app.ingestion.engine import RepositoryIngestionEngine
from backend.app.sources.registry import RepositoryRegistry


def _create_multi_contributor_repo(root: Path):
    """Initializes a real git repository with multiple commits and contributors."""
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alice Dev"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alice@example.com"], cwd=str(root), check=True, capture_output=True)

    # Commit 1: Core layer (Alice)
    core_dir = root / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "__init__.py").write_text("# core\n", encoding="utf-8")
    (core_dir / "config.py").write_text("class AppConfig:\n    PORT = 8080\n", encoding="utf-8")
    (core_dir / "database.py").write_text(
        "from core.config import AppConfig\n\nclass DatabaseConnection:\n    pass\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add core config and database"], cwd=str(root), check=True, capture_output=True
    )

    # Commit 2: Auth service (Bob)
    subprocess.run(["git", "config", "user.name", "Bob Engineer"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bob@example.com"], cwd=str(root), check=True, capture_output=True)
    services_dir = root / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    (services_dir / "__init__.py").write_text("# services\n", encoding="utf-8")
    auth_code = (
        "from core.database import DatabaseConnection\n"
        "from core.config import AppConfig\n\n"
        "class AuthService:\n    pass\n"
    )
    (services_dir / "auth.py").write_text(auth_code, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add auth service"], cwd=str(root), check=True, capture_output=True)

    # Commit 3: Billing service (Charlie)
    subprocess.run(["git", "config", "user.name", "Charlie Architect"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "charlie@example.com"], cwd=str(root), check=True, capture_output=True
    )
    (services_dir / "billing.py").write_text(
        "from services.auth import AuthService\n\nclass BillingService:\n    pass\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add billing service"], cwd=str(root), check=True, capture_output=True)

    # Commit 4: API gateway & utilities (Alice)
    subprocess.run(["git", "config", "user.name", "Alice Dev"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alice@example.com"], cwd=str(root), check=True, capture_output=True)
    api_dir = root / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "__init__.py").write_text("# api\n", encoding="utf-8")
    gw_code = (
        "from services.billing import BillingService\n"
        "from services.auth import AuthService\n"
        "from core.config import AppConfig\n\n"
        "class APIGateway:\n    pass\n"
    )
    (api_dir / "gateway.py").write_text(gw_code, encoding="utf-8")
    utils_dir = root / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)
    (utils_dir / "__init__.py").write_text("# utils\n", encoding="utf-8")
    (utils_dir / "formatter.py").write_text("class Formatter:\n    pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add api gateway and formatter utility"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_end_to_end_complete_investigation_lifecycle(tmp_path: Path):
    """Executes the complete NexusAct lifecycle from repository ingestion to investigation and simulation."""
    repo_root = tmp_path / "sample_ecommerce_repo"
    repo_root.mkdir()
    _create_multi_contributor_repo(repo_root)

    test_graph = f"test_e2e_{uuid.uuid4().hex[:8]}"

    try:
        # 1. Register repository
        registry_file = tmp_path / "test_registry.json"
        registry = RepositoryRegistry(cache_file=registry_file)
        repo_rec = registry.register_local_repository(
            local_path=str(repo_root),
            display_name="Sample Ecommerce",
            custom_graph_name=test_graph,
        )
        assert repo_rec.graph_name == test_graph

        # 2. Ingest repository into isolated FalkorDB graph
        engine = RepositoryIngestionEngine(graph_client)
        report = engine.ingest(repo_path=str(repo_root), graph_name=test_graph, repo_id=repo_rec.id)
        assert report.status == "COMPLETED"
        assert report.module_count >= 5
        assert report.import_edge_count >= 5

        # 3. Verify graph nodes and relationships
        modules_res = graph_client.query(
            f"MATCH (m:{LABEL_MODULE}) RETURN m.name ORDER BY m.name", graph_name=test_graph
        )
        module_names = [row[0] for row in modules_res]
        assert "api.gateway" in module_names
        assert "services.auth" in module_names
        assert "services.billing" in module_names
        assert "core.database" in module_names
        assert "core.config" in module_names

        # 4. Natural-language entity resolution
        res_output = execute_resolve_entity(
            ResolveEntityInput(
                query="Which components will break if the auth service is refactored?",
                graph_name=test_graph,
            )
        )
        assert res_output.resolved_id == "mod:services.auth"
        assert res_output.confidence in ("EXACT", "HIGH")

        # 5. Reverse dependency impact analysis
        impact_out = execute_trace_impact(
            TraceImpactInput(
                module_identifier="mod:services.auth",
                graph_name=test_graph,
                max_depth=3,
            )
        )
        assert impact_out.target_module_id == "mod:services.auth"
        impacted_ids = [m.module_id for m in impact_out.impacted_modules]
        assert "mod:services.billing" in impacted_ids
        assert "mod:api.gateway" in impacted_ids

        # 6. Contributor knowledge scoring
        who_out = execute_who_knows(
            WhoKnowsInput(
                module_identifier="mod:services.auth",
                graph_name=test_graph,
            )
        )
        assert len(who_out.candidates) >= 1
        top_reviewer = who_out.candidates[0]
        # Bob authored the auth service commit
        assert "bob" in top_reviewer.name.lower() or "bob" in top_reviewer.email.lower()
        assert top_reviewer.composite_score > 0.0

        # For isolated module utils.formatter, verify author Alice is returned without fake peer review
        utils_who = execute_who_knows(
            WhoKnowsInput(
                module_identifier="mod:utils.formatter",
                graph_name=test_graph,
            )
        )
        assert len(utils_who.candidates) >= 1
        assert "alice" in utils_who.candidates[0].name.lower()

        # 7. Counterfactual simulation: remove services.auth
        pre_nodes = graph_client.query(f"MATCH (m:{LABEL_MODULE}) RETURN count(m)", graph_name=test_graph)[0][0]
        pre_edges = graph_client.query(f"MATCH ()-[r:{REL_DEPENDS_ON}]->() RETURN count(r)", graph_name=test_graph)[0][
            0
        ]

        sim_result = execute_simulate_remove_module(
            SimulateRemoveModuleInput(
                module_identifier="mod:services.auth",
                graph_name=test_graph,
            )
        )
        assert sim_result.target_module_id == "mod:services.auth"
        assert sim_result.disappeared_paths_count > 0
        assert sim_result.surviving_paths_count > 0
        assert 0.0 < sim_result.blast_radius_score <= 1.0

        # Confirm the source graph is completely intact and unaffected
        post_nodes = graph_client.query(f"MATCH (m:{LABEL_MODULE}) RETURN count(m)", graph_name=test_graph)[0][0]
        post_edges = graph_client.query(f"MATCH ()-[r:{REL_DEPENDS_ON}]->() RETURN count(r)", graph_name=test_graph)[0][
            0
        ]
        assert post_nodes == pre_nodes, "Original graph was mutated by simulation!"
        assert post_edges == pre_edges, "Original relationships were mutated by simulation!"

        # 8. Adaptive Investigation Agent loop
        agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=4)
        agent_report = await agent.investigate(
            question="What is the impact if the auth module fails?",
            module_identifier=None,
            graph_name=test_graph,
        )
        assert agent_report.status == "COMPLETED"
        assert agent_report.target_module_id == "mod:services.auth"
        assert agent_report.verification is not None
        assert agent_report.verification.status == "VERIFIED"
        assert len(agent_report.steps) >= 2

        # 9. Idempotent repeated ingestion
        re_report = engine.ingest(repo_path=str(repo_root), graph_name=test_graph, repo_id=repo_rec.id)
        assert re_report.status == "COMPLETED"
        assert re_report.module_count == report.module_count
        assert re_report.import_edge_count == report.import_edge_count

    finally:
        try:
            graph_client.delete_graph(test_graph, force=True)
        except Exception:
            pass


def test_end_to_end_edge_cases_and_security(tmp_path: Path):
    """Tests edge cases: empty repo, syntax errors, and symlink containment bounds."""
    # 1. Empty repository
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    parser = RepositoryAstParser(str(empty_repo))
    parser.parse_all()
    assert len(parser.module_map) == 0

    # 2. Syntax error in a file does not abort other valid files
    mixed_repo = tmp_path / "mixed_repo"
    mixed_repo.mkdir()
    (mixed_repo / "valid.py").write_text("x = 1\n", encoding="utf-8")
    (mixed_repo / "broken.py").write_text("def broken_syntax(:\n", encoding="utf-8")

    mixed_parser = RepositoryAstParser(str(mixed_repo))
    mixed_parser.parse_all()
    assert "valid" in mixed_parser.module_map
    assert any("broken.py" in s["file"] for s in mixed_parser.skipped_files)

    # 3. Symlink containment
    secret_dir = tmp_path / "outside_dir"
    secret_dir.mkdir()
    (secret_dir / "secret.py").write_text("SECRET = 'outside'\n", encoding="utf-8")

    link_repo = tmp_path / "link_repo"
    link_repo.mkdir()
    (link_repo / "main.py").write_text("import sys\n", encoding="utf-8")

    # Create symlink pointing outside
    try:
        symlink_target = link_repo / "escaped.py"
        symlink_target.symlink_to(secret_dir / "secret.py")
        link_parser = RepositoryAstParser(str(link_repo))
        files = link_parser.discover_files()
        assert symlink_target not in files
        assert any("escaping repository root" in w for w in link_parser.parser_warnings)
    except (OSError, NotImplementedError):
        # Symlink creation may require elevated privileges on some Windows setups
        pass
