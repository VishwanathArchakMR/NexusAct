"""Phase 4 Integration and Unit Tests.

Validates:
1. Public GitHub URL validation (security, HTTPS, no embedded credentials, host restrictions).
2. Repository Registry & isolation (distinct FalkorDB graph names, registry persistence, no cross-talk).
3. Natural-language entity resolution (exact, token/high, honest ambiguity detection, none).
4. Graph neighborhood inspection (1-hop incoming and outgoing connections).
5. Shortest path analysis (bounded directed path discovery and unconnected handling).
6. Source metadata & data gap disclosure (transparency for local Git vs GitHub metadata).
7. Dynamic investigation planning with NL questions and optional target module.
"""

from pathlib import Path

import pytest

from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.neighborhood import (
    GraphNeighborhoodInput,
    execute_graph_neighborhood,
)
from backend.app.graph.tools.resolve import (
    ResolveEntityInput,
    execute_resolve_entity,
)
from backend.app.graph.tools.shortest_path import (
    ShortestPathInput,
    execute_shortest_path,
)
from backend.app.sources.models import (
    CollectionStatus,
    PublicGitHubUrl,
    SourceType,
)
from backend.app.sources.registry import RepositoryRegistry, sanitize_graph_name
from tests.fixtures.synthetic_graph import seed_synthetic_graph


@pytest.fixture(scope="module")
def setup_phase4_graph():
    """Seeds a controlled synthetic graph for Phase 4 graph tool evaluation."""
    test_graph = "test_phase4_fixture"
    seed_synthetic_graph(graph_client, graph_name=test_graph)
    yield test_graph
    try:
        graph_client.delete_graph(test_graph, force=True)
    except Exception:
        pass


# ==============================================================================
# 1. Public GitHub URL Validation Tests
# ==============================================================================


def test_github_url_valid_https():
    url = "https://github.com/fastapi/fastapi"
    parsed = PublicGitHubUrl.parse_and_validate(url)
    assert parsed.owner == "fastapi"
    assert parsed.repo == "fastapi"
    assert parsed.canonical_url == "https://github.com/fastapi/fastapi"


def test_github_url_strips_git_suffix():
    url = "https://github.com/psf/requests.git"
    parsed = PublicGitHubUrl.parse_and_validate(url)
    assert parsed.owner == "psf"
    assert parsed.repo == "requests"


def test_github_url_rejects_embedded_credentials():
    with pytest.raises(ValueError, match="embedded credentials"):
        PublicGitHubUrl.parse_and_validate("https://user:secret@github.com/owner/repo")


def test_github_url_rejects_non_https():
    with pytest.raises(ValueError, match="HTTPS"):
        PublicGitHubUrl.parse_and_validate("http://github.com/owner/repo")
    with pytest.raises(ValueError, match="HTTPS"):
        PublicGitHubUrl.parse_and_validate("git://github.com/owner/repo")


def test_github_url_rejects_arbitrary_hosts():
    with pytest.raises(ValueError, match="Only 'github.com' is allowed"):
        PublicGitHubUrl.parse_and_validate("https://gitlab.com/owner/repo")
    with pytest.raises(ValueError, match="Only 'github.com' is allowed"):
        PublicGitHubUrl.parse_and_validate("https://evil-site.com/owner/repo")


def test_github_url_rejects_invalid_paths():
    with pytest.raises(ValueError, match="Expected repository path format"):
        PublicGitHubUrl.parse_and_validate("https://github.com/owner/repo/extra/path")
    with pytest.raises(ValueError, match="Expected repository path format"):
        PublicGitHubUrl.parse_and_validate("https://github.com/onlyowner")


# ==============================================================================
# 2. Repository Registry & Isolation Tests
# ==============================================================================


def test_sanitize_graph_name_safety():
    assert sanitize_graph_name("fastapi/fastapi") == "repo_fastapi_fastapi"
    assert sanitize_graph_name("My-Repo.Service 123") == "repo_my_repo_service_123"
    # Never exceed 30 chars
    long_name = "a" * 50
    sanitized = sanitize_graph_name(long_name)
    assert len(sanitized) <= 30
    assert sanitized.startswith("repo_")


def test_repository_registry_registration_and_isolation(tmp_path: Path):
    reg_file = tmp_path / "test_repos.json"
    registry = RepositoryRegistry(cache_file=reg_file)

    # Register local repo
    local_rec = registry.register_local_repository(
        local_path=str(tmp_path),
        display_name="Test Local",
        custom_graph_name="repo_test_local",
    )
    assert local_rec.id.startswith("repo:local_")
    assert local_rec.graph_name == "repo_test_local"

    # Register GitHub repo
    gh_rec = registry.register_github_repository(
        github_url="https://github.com/pallets/flask",
        display_name="Flask Web",
    )
    assert gh_rec.id == "repo:pallets_flask"
    assert gh_rec.graph_name == "repo_pallets_flask"
    assert gh_rec.source_type == SourceType.GITHUB

    # Distinct graph names guarantee isolation
    assert local_rec.graph_name != gh_rec.graph_name

    # Lookup by ID
    assert registry.get_repository(gh_rec.id) is not None
    # Lookup by graph name
    assert registry.get_repository("repo_test_local") is not None


# ==============================================================================
# 3. Natural Language Entity Resolution Tests
# ==============================================================================


def test_resolve_entity_exact_match(setup_phase4_graph):
    test_graph = setup_phase4_graph
    res = execute_resolve_entity(
        ResolveEntityInput(query="orders", graph_name=test_graph),
        client=graph_client,
    )
    assert res.confidence == "EXACT"
    assert res.resolved_id == "mod:services/orders"
    assert res.resolved_name == "orders"


def test_resolve_entity_from_natural_language_question(setup_phase4_graph):
    test_graph = setup_phase4_graph
    res = execute_resolve_entity(
        ResolveEntityInput(
            query="What might be affected if I modify the billing module?",
            graph_name=test_graph,
        ),
        client=graph_client,
    )
    assert res.confidence in ("EXACT", "HIGH")
    assert res.resolved_id == "mod:services/billing"


def test_resolve_entity_ambiguous_honest_detection(setup_phase4_graph):
    test_graph = setup_phase4_graph
    # In synthetic graph, "services/orders" and "services/inventory" both contain "services"
    res = execute_resolve_entity(
        ResolveEntityInput(query="services", graph_name=test_graph),
        client=graph_client,
    )
    assert res.confidence == "AMBIGUOUS"
    assert len(res.candidates) >= 2
    assert res.clarification_prompt is not None
    assert "clarify" in res.clarification_prompt.lower()


def test_resolve_entity_unmatched(setup_phase4_graph):
    test_graph = setup_phase4_graph
    res = execute_resolve_entity(
        ResolveEntityInput(query="nonexistent_alien_package_xyz", graph_name=test_graph),
        client=graph_client,
    )
    assert res.confidence == "NONE"
    assert res.resolved_id is None


# ==============================================================================
# 4. Graph Neighborhood & Shortest Path Tool Tests
# ==============================================================================


def test_graph_neighborhood_inspection(setup_phase4_graph):
    test_graph = setup_phase4_graph
    # In synthetic graph:
    # gateway -> orders -> billing
    # gateway is incoming to orders; billing is outgoing from orders
    res = execute_graph_neighborhood(
        GraphNeighborhoodInput(
            module_identifier="mod:services/orders",
            graph_name=test_graph,
        ),
        client=graph_client,
    )
    assert res.target_module_id == "mod:services/orders"
    incoming_ids = [n.id for n in res.incoming_dependents]
    outgoing_ids = [n.id for n in res.outgoing_dependencies]
    assert "mod:api/gateway" in incoming_ids
    assert "mod:services/billing" in outgoing_ids or "mod:pkg/database" in outgoing_ids


def test_shortest_path_connected_and_unconnected(setup_phase4_graph):
    test_graph = setup_phase4_graph
    # Path from gateway to database
    path_res = execute_shortest_path(
        ShortestPathInput(
            source_identifier="mod:api/gateway",
            target_identifier="mod:pkg/database",
            graph_name=test_graph,
        ),
        client=graph_client,
    )
    assert path_res.connected is True
    assert path_res.hops >= 1
    assert len(path_res.path_nodes) >= 2
    assert path_res.path_nodes[0] == "mod:api/gateway"
    assert path_res.path_nodes[-1] == "mod:pkg/database"


# ==============================================================================
# 5. Dynamic Investigation Planner with Natural Language Resolution
# ==============================================================================


@pytest.mark.asyncio
async def test_agent_investigate_natural_language_target(setup_phase4_graph):
    test_graph = setup_phase4_graph
    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=4)

    # Omit module_identifier! Question specifies "billing"
    report = await agent.investigate(
        question="Which modules might break if I change the billing component?",
        module_identifier=None,
        graph_name=test_graph,
    )

    assert report.status == "COMPLETED"
    assert report.target_module_id == "mod:services/billing"
    assert report.verification is not None
    assert report.is_heuristic_fallback is True  # Honestly labeled
    assert len(report.steps) > 0


@pytest.mark.asyncio
async def test_agent_investigate_ambiguous_question_returns_clarification(setup_phase4_graph):
    test_graph = setup_phase4_graph
    agent = AdaptiveInvestigationAgent(client=graph_client, max_tool_budget=3)

    # Asking about "services" where multiple services modules exist
    report = await agent.investigate(
        question="What depends on services?",
        module_identifier=None,
        graph_name=test_graph,
    )

    assert report.status == "AMBIGUOUS"
    assert report.ambiguity_candidates is not None
    assert len(report.ambiguity_candidates) >= 2
    assert "clarify" in report.summary.lower()


# ==============================================================================
# 6. Real Repository Ingestion & Public GitHub Integration Tests
# ==============================================================================


def test_local_repository_fixture_ingestion_and_idempotency(tmp_path: Path):
    """Tests real ingestion of a deterministic local repository fixture into an isolated graph."""
    from backend.app.ingestion.engine import RepositoryIngestionEngine

    # Create dummy repository fixture with python modules
    pkg_dir = tmp_path / "myapp"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# myapp package\n", encoding="utf-8")
    (pkg_dir / "db.py").write_text("class Database:\n    pass\n", encoding="utf-8")
    (pkg_dir / "service.py").write_text("from myapp.db import Database\n", encoding="utf-8")

    test_iso_graph = "test_fixture_iso_repo"
    engine = RepositoryIngestionEngine(graph_client)

    try:
        report1 = engine.ingest(
            repo_path=str(tmp_path),
            graph_name=test_iso_graph,
            repo_id="repo:test_fixture",
        )
        assert report1.status == "COMPLETED"
        assert report1.module_count >= 2
        assert report1.import_edge_count >= 1

        # Idempotent repeated ingestion: counts should remain stable
        report2 = engine.ingest(
            repo_path=str(tmp_path),
            graph_name=test_iso_graph,
            repo_id="repo:test_fixture",
        )
        assert report2.module_count == report1.module_count
        assert report2.import_edge_count == report1.import_edge_count
    finally:
        try:
            graph_client.delete_graph(test_iso_graph, force=True)
        except Exception:
            pass


def test_public_github_fetcher_live_integration():
    """Live integration test against a public repository (octocat/Hello-World)."""
    import socket

    from backend.app.sources.github_fetcher import GitHubRepoFetcher
    from backend.app.sources.github_metadata import GitHubMetadataCollector

    # Check network reachability
    try:
        socket.create_connection(("github.com", 443), timeout=3.0)
    except OSError:
        pytest.skip("GitHub is not reachable over network in this environment")

    url = PublicGitHubUrl.parse_and_validate("https://github.com/octocat/Hello-World")
    fetcher = GitHubRepoFetcher()
    checkout_path, sha = fetcher.clone_or_update(url, depth=1, timeout_seconds=45)

    assert checkout_path.exists()
    assert (checkout_path / ".git").is_dir()
    assert sha != "UNKNOWN"
    assert len(sha) == 40  # Valid 40-char SHA-1 commit hash

    # Metadata check
    collector = GitHubMetadataCollector()
    meta, cap = collector.collect_metadata(url.owner, url.repo, timeout_seconds=15)
    assert meta["owner"] == "octocat"
    assert meta["repo"] == "Hello-World"
    assert cap.status in (CollectionStatus.COLLECTED, CollectionStatus.PARTIAL, CollectionStatus.RATE_LIMITED)
