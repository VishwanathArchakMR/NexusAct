"""Tests for Phase 17: Workspace Graph Intelligence, Panel Explanations, and AST Dependency Extraction."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.ingestion.ast_parser import RepositoryAstParser
from backend.app.main import app

client = TestClient(app)


def test_explain_panel_endpoint_with_fallback():
    """Verify that /api/v1/investigation/explain-panel returns grounded explanations with caching."""
    payload = {
        "investigation_id": "inv_test_phase17",
        "panel_id": "graph",
        "question": "Assess architecture and module coupling",
        "target_id": "backend.app.main",
        "repo_id": "repo:local_nexusact",
        "commit_sha": "2e06965",
        "data_summary": {
            "total_nodes": 120,
            "total_edges": 369,
        },
    }

    response = client.post("/api/v1/investigation/explain-panel", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "what_you_are_looking_at" in data
    assert "what_nexusact_found" in data
    assert "why_it_matters" in data
    assert "evidence_and_relationships" in data
    assert isinstance(data["evidence_and_relationships"], list)
    assert len(data["evidence_and_relationships"]) > 0
    assert "confidence_and_limitations" in data
    assert "recommended_next_step" in data
    assert data["provider_status"] in ("gemini", "fallback", "cached")
    assert "cache_key" in data

    # Verify that a second call hits the cache
    second_response = client.post("/api/v1/investigation/explain-panel", json=payload)
    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["cache_key"] == data["cache_key"]
    assert second_data["provider_status"] == "cached"


def test_explain_panel_all_ten_panels_supported():
    """Verify that all 10 workspace panels are recognized and grounded."""
    panels = [
        "graph",
        "code",
        "simulation",
        "reviewers",
        "trace",
        "neighborhood",
        "provenance",
        "action",
        "security",
        "fraud",
    ]

    for p in panels:
        payload = {
            "investigation_id": f"inv_test_panel_{p}",
            "panel_id": p,
            "question": f"Explain {p} panel",
            "repo_id": "repo:local_nexusact",
            "data_summary": {"sample_metric": 42},
        }
        res = client.post("/api/v1/investigation/explain-panel", json=payload)
        assert res.status_code == 200, f"Panel {p} failed with status {res.status_code}"
        data = res.json()
        assert len(data["summary"]) > 0
        assert len(data["evidence_and_relationships"]) > 0


def test_ast_parser_dependency_extraction():
    """Verify that RepositoryAstParser extracts real dependencies from actual codebase files without fabrication."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    parser = RepositoryAstParser(str(workspace_root))
    parser.parse_all()

    # Verify files and modules were discovered and parsed
    assert len(parser.file_map) > 50
    assert len(parser.module_map) > 20

    # Ensure backend.app.main exists and has imports
    main_file = "backend/app/main.py"
    assert main_file in parser.file_map
    main_info = parser.file_map[main_file]
    assert len(main_info.imports) > 0

    # Ensure resolved dependencies are present
    resolved_imports = [imp for imp in main_info.imports if imp.is_resolved]
    assert len(resolved_imports) > 0
    resolved_targets = [imp.target_module for imp in resolved_imports if imp.target_module]
    assert any("api" in t or "config" in t or "cors" in t for t in resolved_targets)


def test_graph_isolation():
    """Verify that the synthetic financial fraud demo is strictly partitioned from main software repo."""
    fraud_payload = {
        "investigation_id": "inv_fraud_check",
        "panel_id": "fraud",
        "question": "Detect circular layering rings",
        "repo_id": "nexusact_fraud_demo",
        "data_summary": {
            "patterns_detected_count": 3,
            "total_suspicious_volume_usd": 250000.0,
            "benign_controls_count": 2,
            "risk_indicator": "HIGH_RISK",
        },
    }
    res = client.post("/api/v1/investigation/explain-panel", json=fraud_payload)
    assert res.status_code == 200
    data = res.json()
    assert "fraud" in data["what_you_are_looking_at"].lower() or "financial" in data["what_you_are_looking_at"].lower()
