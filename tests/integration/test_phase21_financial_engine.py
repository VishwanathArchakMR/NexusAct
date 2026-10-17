"""Phase 21 Integration & Unit Tests: Real-Data Financial Investigation Engine & Cypher Reasoning."""

import pytest

from backend.app.finance.cypher_engine import (
    canonicalize_cycle,
    query_benign_controls,
    query_cycles,
    query_financial_subgraph,
    query_multi_hop_path,
    query_shared_entities,
)
from backend.app.finance.ingestion_engine import (
    ingest_financial_dataset,
    preview_dataset,
    validate_and_parse_rows,
)
from backend.app.finance.investigation_service import execute_financial_investigation
from backend.app.graph.client import graph_client

SAMPLE_CSV_TEXT = (
    "transaction_id,sender_account,receiver_account,amount_usd,timestamp,"
    "device_fingerprint,ip_address,merchant_name,is_fraud\n"
    "TX_001,ACC_ALPHA,ACC_BETA,10000.0,2026-03-01T10:00:00Z,DEV_IPHONE_99,198.51.100.12,MERCH_SWIFT,1\n"
    "TX_002,ACC_BETA,ACC_GAMMA,9500.0,2026-03-01T11:15:00Z,DEV_IPHONE_99,198.51.100.12,MERCH_SWIFT,1\n"
    "TX_003,ACC_GAMMA,ACC_ALPHA,9000.0,2026-03-01T12:30:00Z,DEV_LAPTOP_44,203.0.113.88,MERCH_WIRE,1\n"
    "TX_004,ACC_SAFE_1,ACC_SAFE_2,120.0,2026-03-01T14:00:00Z,DEV_DESKTOP_11,192.0.2.1,MERCH_GROCERY,0\n"
    "TX_005,ACC_SAFE_2,ACC_RETAIL,75.0,2026-03-01T15:30:00Z,DEV_DESKTOP_22,192.0.2.2,MERCH_RETAIL,0\n"
)

MALFORMED_CSV_TEXT = """tx_id,src_account,dst_account,amount
TX_BAD_1,,ACC_BETA,500.0
TX_BAD_2,ACC_ALPHA,,500.0
TX_BAD_3,ACC_ALPHA,ACC_BETA,-100.0
TX_BAD_4,ACC_ALPHA,ACC_BETA,not_a_number
TX_VALID,ACC_ALPHA,ACC_BETA,150.0
"""


def test_csv_profiling_and_schema_mapping():
    """Verify automatic detection and column mapping recommendation."""
    preview = preview_dataset(SAMPLE_CSV_TEXT, filename="test_aml.csv")
    assert len(preview.detected_columns) == 9
    suggested_mapping = preview.suggested_mapping
    assert suggested_mapping.transaction_id == "transaction_id"
    assert suggested_mapping.source_account == "sender_account"
    assert suggested_mapping.destination_account == "receiver_account"
    assert suggested_mapping.amount == "amount_usd"
    assert suggested_mapping.device_id == "device_fingerprint"
    assert suggested_mapping.ip_address == "ip_address"
    assert suggested_mapping.ground_truth_label == "is_fraud"
    assert len(preview.preview_rows) == 5


def test_validation_rejects_malformed_and_negative_rows():
    """Verify rejection of empty accounts, negative amounts, non-numeric values."""
    preview = preview_dataset(MALFORMED_CSV_TEXT, filename="malformed.csv")
    accepted, rejected, warnings = validate_and_parse_rows(MALFORMED_CSV_TEXT, mapping=preview.suggested_mapping)
    # Only 1 row is valid out of 5
    assert len(accepted) == 1
    assert accepted[0].tx_id == "TX_VALID"
    assert sum(rejected.values()) == 4


def test_cycle_canonicalization():
    """Verify cyclic rotation normalization suppresses duplicate cycle reports."""
    cycle1 = ["ACC_BETA", "ACC_GAMMA", "ACC_ALPHA", "ACC_BETA"]
    cycle2 = ["ACC_GAMMA", "ACC_ALPHA", "ACC_BETA", "ACC_GAMMA"]
    cycle3 = ["ACC_ALPHA", "ACC_BETA", "ACC_GAMMA", "ACC_ALPHA"]

    c1 = canonicalize_cycle(cycle1)
    c2 = canonicalize_cycle(cycle2)
    c3 = canonicalize_cycle(cycle3)

    assert c1 == c2 == c3
    assert c1 == ("ACC_ALPHA", "ACC_BETA", "ACC_GAMMA")


@pytest.mark.asyncio
async def test_financial_ingestion_and_falkordb_isolation():
    """Verify real FalkorDB ingestion in an isolated graph namespace without touching nexusact_main."""
    preview = preview_dataset(SAMPLE_CSV_TEXT, filename="test_aml.csv")
    metadata = ingest_financial_dataset(
        raw_content=SAMPLE_CSV_TEXT,
        filename="test_aml.csv",
        dataset_name="Test AML Run",
        mapping=preview.suggested_mapping,
        client=graph_client,
    )

    # 1. Must use isolated graph namespace
    assert metadata.graph_name.startswith("fin_")
    assert metadata.graph_name != "nexusact_main"
    assert metadata.accepted_rows == 5
    assert metadata.accounts_count >= 5
    assert metadata.has_ground_truth is True

    # 2. Query cycles in the isolated graph
    cycles = query_cycles(metadata.graph_name, min_hops=3, max_hops=4, client=graph_client)
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle.hops == 3
    assert set(cycle.participating_accounts) == {"ACC_ALPHA", "ACC_BETA", "ACC_GAMMA"}
    assert cycle.total_volume_usd == 28500.0

    # 3. Query shared hardware device
    shared = query_shared_entities(metadata.graph_name, client=graph_client, limit=20)
    assert len(shared) >= 1
    device_finding = next((s for s in shared if s.entity_type == "Device"), None)
    assert device_finding is not None
    assert "DEV_IPHONE_99" in device_finding.entity_id
    assert set(device_finding.associated_accounts) == {"ACC_ALPHA", "ACC_BETA"}

    # 4. Multi-hop shortest path
    path = query_multi_hop_path(metadata.graph_name, "ACC_ALPHA", "ACC_GAMMA", client=graph_client)
    assert path is not None
    assert path.source_account == "ACC_ALPHA"
    assert path.destination_account == "ACC_GAMMA"
    assert path.hops == 2

    # 5. Benign controls suppression
    flagged = set(cycle.participating_accounts)
    benigns = query_benign_controls(metadata.graph_name, flagged_accounts=flagged, client=graph_client)
    assert len(benigns) >= 1
    assert any("SAFE" in b.account_id for b in benigns)

    # 6. Full Financial Investigation Service Execution
    result = execute_financial_investigation(
        dataset_id=metadata.dataset_id,
        client=graph_client,
    )
    assert result.investigation_id.startswith("inv_fin_")
    assert len(result.findings) >= 2
    assert result.risk_score > 0.5
    assert len(result.risk_factors) >= 2
    # Check that each finding contains supporting Cypher query and evidence records
    for f in result.findings:
        assert len(f.cypher_query_used) > 5
        assert "MATCH" in f.cypher_query_used

    # 7. Subgraph generation with distinct entity colors
    subgraph = query_financial_subgraph(metadata.graph_name, limit=50, client=graph_client)
    assert len(subgraph["nodes"]) >= 5
    assert len(subgraph["edges"]) >= 4
    node_types = {n["type"] for n in subgraph["nodes"]}
    assert "Account" in node_types
    assert "Transaction" in node_types

    # Clean up test graph from FalkorDB
    try:
        graph_client.query("MATCH (n) DETACH DELETE n", graph_name=metadata.graph_name)
    except Exception:
        pass


def test_read_only_guarantee():
    """Verify that the financial investigation service enforces read-only behavior."""
    # Check that execution returns findings with recommendations for human review,
    # and has no account freeze / money transfer calls.
    service_code = open("backend/app/finance/investigation_service.py", encoding="utf-8").read()
    assert "execute_freeze" not in service_code.lower()
    assert "freeze_account" not in service_code.lower()
    assert "transfer_funds" not in service_code.lower()
    assert "Perform human compliance review" in service_code
    assert "does not execute account freezes" in service_code.lower()
