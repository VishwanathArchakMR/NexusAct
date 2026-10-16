"""Phase 8 Graph Truth, Investigation Repair, and Deduplication Tests.

Verifies:
1. Unresolved target modules return structured UNRESOLVED reports with candidate suggestions,
   instead of raising uncaught 400 exceptions or masquerading previous results.
2. Repositories with no Python source files produce an honest diagnostic gap notice.
3. Universal Discovery Planner deduplicates entities by canonical DOI across providers.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from backend.app.agent.discovery_planner import UniversalDiscoveryPlanner, UniversalInvestigationPlan
from backend.app.agent.llm import NoneLLMProvider
from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.ingestion.engine import RepositoryIngestionEngine
from backend.app.sources.connector_registry import ConnectorRegistry, SourceRecord, SourceRelationship


@pytest.mark.asyncio
async def test_unresolved_target_returns_structured_report():
    """Verify that an unresolved target returns an honest UNRESOLVED report with zero invented paths."""
    agent = AdaptiveInvestigationAgent(NoneLLMProvider())

    report = await agent.investigate(
        question="What is the impact of missing_module?",
        module_identifier="mod:completely_fictional_module_xyz",
        graph_name="nexusact_test_nonexistent",
    )

    assert report.status == "UNRESOLVED"
    assert report.unresolved_reason is not None
    assert "cannot be resolved" in report.unresolved_reason.lower()
    assert report.target_module_id == "mod:completely_fictional_module_xyz"
    # Zero fabricated paths or callers
    assert report.impact_result is None
    assert report.simulation_result is None
    assert report.reviewer_result is None


def test_empty_python_repo_produces_honest_diagnostic_gap(tmp_path):
    """Verify that a repository with no .py files explicitly records diagnostic gaps."""
    # Create a non-Python repository (e.g. React/TypeScript only)
    repo_dir = tmp_path / "ts_project"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name": "test"}', encoding="utf-8")
    (repo_dir / "App.tsx").write_text("export const App = () => <div>Hello</div>;", encoding="utf-8")

    # Initialize git repo in tmp_path so GitHistoryExtractor works
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    engine = RepositoryIngestionEngine()
    result = engine.ingest(repo_path=str(repo_dir), graph_name="nexusact_test_empty_ts")

    assert result.module_count == 0
    assert result.import_edge_count == 0
    # Must explicitly state in data_gaps why 0 modules were found
    assert any("No supported Python source files" in gap for gap in result.data_gaps)


def test_discovery_planner_canonical_doi_deduplication():
    """Verify that multiple records sharing the same normalized DOI are deduplicated canonically."""
    planner = UniversalDiscoveryPlanner()

    # Provider 1 (OpenAlex) returns paper with DOI 10.1234/test.5678
    rec1 = SourceRecord(
        source_id="openalex",
        external_id="W12345",
        entity_type="Paper",
        canonical_url="https://doi.org/10.1234/test.5678",
        data={"title": "Attention Is All You Need", "doi": "10.1234/test.5678"},
        relationships=[
            SourceRelationship(
                relation_type="CITES",
                source_entity_id="openalex:W12345",
                target_entity_id="hf:transformer-model",
                evidence_field="references",
                confidence="SUPPORTED",
            )
        ],
    )

    # Provider 2 (Crossref) returns the exact same paper with identical DOI
    rec2 = SourceRecord(
        source_id="crossref",
        external_id="10.1234/test.5678",
        entity_type="Paper",
        canonical_url="https://doi.org/10.1234/test.5678",
        data={"title": "Attention Is All You Need (Crossref Title)", "doi": "https://doi.org/10.1234/test.5678"},
        relationships=[
            SourceRelationship(
                relation_type="CITES",
                source_entity_id="crossref:10.1234/test.5678",
                target_entity_id="hf:transformer-model",
                evidence_field="relation",
                confidence="SUPPORTED",
            )
        ],
    )

    # Hugging Face returns the model
    rec3 = SourceRecord(
        source_id="huggingface",
        external_id="transformer-model",
        entity_type="Model",
        canonical_url="https://huggingface.co/transformer-model",
        data={"name": "transformer-model"},
        relationships=[],
    )

    from backend.app.sources.connector_registry import ConnectorResult

    mock_conn_alex = MagicMock()
    mock_conn_alex.search.return_value = ConnectorResult(source_id="openalex", records=[rec1])
    mock_conn_cross = MagicMock()
    mock_conn_cross.search.return_value = ConnectorResult(source_id="crossref", records=[rec2])
    mock_conn_hf = MagicMock()
    mock_conn_hf.search.return_value = ConnectorResult(source_id="huggingface", records=[rec3])

    def mock_get(source_id: str):
        if source_id == "openalex":
            return mock_conn_alex
        elif source_id == "crossref":
            return mock_conn_cross
        elif source_id == "huggingface":
            return mock_conn_hf
        return None

    mock_persister = MagicMock()
    mock_persister.persist_records.return_value = {"entities": 2, "source_records": 2, "relationships": 1}
    mock_persister.find_path.return_value = []
    mock_persister.get_subgraph.return_value = {"nodes": [], "edges": [], "total_nodes": 2, "total_edges": 1}

    planner = UniversalDiscoveryPlanner(persister=mock_persister)

    custom_plan = UniversalInvestigationPlan(
        question="Find transformer models and papers",
        target_entity_types=["Model", "Paper"],
        relationship_focus=["CITES"],
        selected_source_ids=["openalex", "crossref", "huggingface"],
        search_keywords=["transformer"],
        max_results_per_source=5,
        traversal_depth=2,
        is_heuristic_fallback=True,
    )

    with patch.object(ConnectorRegistry, "get", side_effect=mock_get):
        result = planner.execute_investigation(
            question="Find transformer models and papers",
            plan_override=custom_plan,
        )

        # Verify deduplication: 1 paper + 1 model = 2 entities, not 3
        paper_entities = [e for e in result.entities if e.get("id") == "doi:10.1234/test.5678"]
        assert len(paper_entities) == 1
        assert len(result.entities) == 2

        # Relationships should also be deduplicated by canonical source/type/target
        assert len(result.relationships) == 1
        assert result.relationships[0]["source"] == "doi:10.1234/test.5678"
