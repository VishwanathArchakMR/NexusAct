"""Tests for Universal Public-Data Connectors, FalkorDB Persistence, and Ask GAF."""

from __future__ import annotations

import json
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.discovery_planner import (
    UniversalDiscoveryPlanner,
)
from backend.app.graph.client import graph_client
from backend.app.main import create_app
from backend.app.sources.connector_registry import (
    ConnectorQuery,
    ConnectorRegistry,
    SourceRecord,
    SourceRelationship,
)
from backend.app.sources.connectors.crossref import CrossrefConnector
from backend.app.sources.connectors.huggingface import HuggingFaceConnector
from backend.app.sources.connectors.openalex import OpenAlexConnector
from backend.app.sources.connectors.wikidata import WikidataConnector
from backend.app.sources.graph_persister import PublicGraphPersister

TEST_PUBLIC_GRAPH = "nexusact_public_test"


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture
def test_persister() -> Generator[PublicGraphPersister, None, None]:
    persister = PublicGraphPersister(client=graph_client, graph_name=TEST_PUBLIC_GRAPH)
    persister.ensure_schema()
    yield persister
    try:
        graph_client.delete_graph(TEST_PUBLIC_GRAPH)
    except Exception:
        pass


def test_connector_registry_initialization():
    """Verifies that all 4 default public connectors are registered with stable properties."""
    ConnectorRegistry.init_defaults()
    source_ids = ConnectorRegistry.all_source_ids()

    assert "huggingface" in source_ids
    assert "openalex" in source_ids
    assert "crossref" in source_ids
    assert "wikidata" in source_ids

    # Entity type filtering
    model_conns = ConnectorRegistry.select_for_entity_types(["Model"])
    assert any(c.SOURCE_ID == "huggingface" for c in model_conns)

    paper_conns = ConnectorRegistry.select_for_entity_types(["Paper"])
    assert any(c.SOURCE_ID == "openalex" for c in paper_conns)
    assert any(c.SOURCE_ID == "crossref" for c in paper_conns)


def test_huggingface_connector_parsing():
    """Validates deterministic parsing of Hugging Face model and dataset records."""
    connector = HuggingFaceConnector()

    mock_models_response = [
        {
            "id": "meta-llama/Llama-3-8B",
            "author": "meta-llama",
            "pipeline_tag": "text-generation",
            "tags": ["llama", "dataset:squad", "license:llama3"],
            "likes": 5000,
            "downloads": 1000000,
        }
    ]

    with patch.object(connector, "_http_get", return_value=(200, mock_models_response)):
        query = ConnectorQuery(query_text="llama-3", entity_types=["Model"], max_results=5)
        result = connector.search(query)

        assert result.source_id == "huggingface"
        assert len(result.records) == 1
        rec = result.records[0]

        assert rec.entity_type == "Model"
        assert rec.external_id == "meta-llama/Llama-3-8B"
        assert rec.canonical_url == "https://huggingface.co/meta-llama/Llama-3-8B"
        assert rec.data["author"] == "meta-llama"

        # Check supported relationships
        rel_types = {r.relation_type for r in rec.relationships}
        assert "CREATED_BY" in rel_types
        assert "USES_DATASET" in rel_types

        ds_rel = next(r for r in rec.relationships if r.relation_type == "USES_DATASET")
        assert ds_rel.target_entity_id == "huggingface:squad"
        assert ds_rel.confidence == "SUPPORTED"


def test_openalex_connector_parsing_and_doi_normalization():
    """Validates OpenAlex works parsing, author affiliation, and lowercase DOI normalization."""
    connector = OpenAlexConnector()

    mock_work = {
        "id": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.48550/arXiv.1706.03762",
        "title": "Attention Is All You Need",
        "publication_year": 2017,
        "cited_by_count": 95000,
        "authorships": [
            {
                "author": {"id": "https://openalex.org/A5023880814", "display_name": "Ashish Vaswani"},
                "institutions": [{"id": "https://openalex.org/I1291425158", "display_name": "Google"}],
            }
        ],
        "topics": [{"display_name": "Natural Language Processing"}],
        "referenced_works": ["https://openalex.org/W1965994589"],
    }

    with patch.object(connector, "_http_get", return_value=(200, {"results": [mock_work]})):
        query = ConnectorQuery(query_text="Attention Is All You Need", max_results=2)
        result = connector.search(query)

        assert len(result.records) == 1
        rec = result.records[0]
        assert rec.entity_type == "Paper"
        # DOI normalized to lowercase without URL scheme
        assert rec.external_id == "10.48550/arxiv.1706.03762"
        assert rec.data["publication_year"] == 2017

        rel_types = {r.relation_type for r in rec.relationships}
        assert "AUTHORED" in rel_types
        assert "AFFILIATED_WITH" in rel_types
        assert "HAS_TOPIC" in rel_types
        assert "CITES" in rel_types


def test_crossref_connector_parsing_and_funding():
    """Validates Crossref parsing, author affiliations, and funding evidence."""
    connector = CrossrefConnector()

    mock_item = {
        "DOI": "10.1145/3292500.3330962",
        "title": ["Knowledge Graph Convolutional Networks"],
        "author": [
            {
                "given": "Hongwei",
                "family": "Wang",
                "affiliation": [{"name": "Stanford University"}],
            }
        ],
        "funder": [{"name": "National Science Foundation"}],
        "reference": [{"DOI": "10.1145/1234.5678"}],
        "published": {"date-parts": [[2019, 7]]},
    }

    with patch.object(connector, "_http_get", return_value=(200, {"message": {"items": [mock_item]}})):
        query = ConnectorQuery(query_text="Knowledge Graph Convolutional", max_results=2)
        result = connector.search(query)

        assert len(result.records) == 1
        rec = result.records[0]
        assert rec.entity_type == "Paper"
        assert rec.external_id == "10.1145/3292500.3330962"

        rel_types = {r.relation_type for r in rec.relationships}
        assert "AUTHORED" in rel_types
        assert "AFFILIATED_WITH" in rel_types
        assert "FUNDED_BY" in rel_types
        assert "CITES" in rel_types


def test_wikidata_connector_controlled_properties():
    """Validates Wikidata entity parsing using controlled property mappings and QIDs."""
    connector = WikidataConnector()

    mock_claims = {
        "P108": [
            {
                "mainsnak": {
                    "datavalue": {"type": "wikibase-entityid", "value": {"id": "Q95"}},
                },
                "rank": "preferred",
                "references": [{"snaks": {}}],
            }
        ],
        "P361": [
            {
                "mainsnak": {
                    "datavalue": {"type": "wikibase-entityid", "value": {"id": "Q11660"}},
                },
                "rank": "normal",
            }
        ],
    }
    mock_entity = {
        "labels": {"en": {"value": "Geoffrey Hinton"}},
        "descriptions": {"en": {"value": "British-Canadian cognitive psychologist and computer scientist"}},
        "claims": mock_claims,
    }

    rec = connector._parse_entity_detail("Q92764", mock_entity)
    assert rec.entity_type == "Person"
    assert rec.external_id == "Q92764"
    assert rec.canonical_url == "https://www.wikidata.org/wiki/Q92764"

    # P108 is mapped to AFFILIATED_WITH with HIGH confidence due to preferred rank and references
    rel = next(r for r in rec.relationships if r.target_entity_id == "wikidata:Q95")
    assert rel.relation_type == "AFFILIATED_WITH"
    assert rel.confidence == "HIGH"


def test_falkordb_public_graph_idempotent_persistence(test_persister: PublicGraphPersister):
    """Verifies that public entities, source records, and relationships persist idempotently."""
    rec = SourceRecord(
        source_id="huggingface",
        entity_type="Model",
        external_id="meta-llama/Llama-3-8B",
        canonical_url="https://huggingface.co/meta-llama/Llama-3-8B",
        data={"name": "Llama-3-8B", "author": "meta-llama"},
        relationships=[
            SourceRelationship(
                relation_type="USES_DATASET",
                source_entity_id="huggingface:meta-llama/Llama-3-8B",
                target_entity_id="huggingface:squad",
                evidence_field="tags.dataset",
                confidence="SUPPORTED",
            )
        ],
    )
    rec.compute_hash(json.dumps(rec.data))

    # First persistence
    counts1 = test_persister.persist_records([rec])
    assert counts1["entities"] == 1
    assert counts1["relationships"] == 1

    # Second persistence (idempotency check)
    counts2 = test_persister.persist_records([rec])
    assert counts2["entities"] == 1

    # Verify nodes in FalkorDB
    subgraph = test_persister.get_subgraph(limit=10)
    node_ids = {n["id"] for n in subgraph["nodes"]}
    assert "huggingface:meta-llama/Llama-3-8B" in node_ids
    assert "huggingface:squad" in node_ids


def test_universal_discovery_planner_heuristics():
    """Validates that the discovery planner selects correct sources and bounded parameters."""
    planner = UniversalDiscoveryPlanner()

    # Model query -> Hugging Face + Wikidata
    plan_models = planner.create_plan("Which organizations publish models in NLP?")
    assert "huggingface" in plan_models.selected_source_ids
    assert "Model" in plan_models.target_entity_types

    # Citation query -> OpenAlex + Crossref
    plan_papers = planner.create_plan("Which research papers connect attention mechanisms through citations?")
    assert "openalex" in plan_papers.selected_source_ids
    assert "Paper" in plan_papers.target_entity_types


def test_discovery_api_sources_endpoint(api_client: TestClient):
    """Verifies GET /api/v1/discover/sources endpoint returns all 4 connectors."""
    res = api_client.get("/api/v1/discover/sources")
    assert res.status_code == 200
    data = res.json()
    assert data["total_connectors"] == 4
    assert "huggingface" in data["sources"]
    assert "openalex" in data["sources"]


def test_discovery_api_ask_gaf_endpoint(api_client: TestClient):
    """Verifies POST /api/v1/discover/ask-gaf endpoint executes end-to-end with bounded fixtures."""
    req_body = {
        "question": "Which organizations publish models related to transformer architectures?",
        "selected_sources": ["huggingface"],
        "max_results": 2,
    }

    mock_rec = SourceRecord(
        source_id="huggingface",
        entity_type="Model",
        external_id="google/bert-base-uncased",
        canonical_url="https://huggingface.co/google/bert-base-uncased",
        data={"name": "bert-base-uncased", "author": "google"},
        relationships=[
            SourceRelationship(
                relation_type="CREATED_BY",
                source_entity_id="huggingface:google/bert-base-uncased",
                target_entity_id="org:huggingface:google",
                evidence_field="author",
                confidence="SUPPORTED",
            )
        ],
    )

    with patch.object(HuggingFaceConnector, "search") as mock_search:
        from backend.app.sources.connector_registry import ConnectorResult

        mock_search.return_value = ConnectorResult(
            source_id="huggingface",
            records=[mock_rec],
            total_available=1,
        )

        res = api_client.post("/api/v1/discover/ask-gaf", json=req_body)
        assert res.status_code == 200
        data = res.json()
        assert data["question"] == req_body["question"]
        assert len(data["entities"]) == 1
        assert len(data["relationships"]) == 1
        assert data["relationships"][0]["type"] == "CREATED_BY"
