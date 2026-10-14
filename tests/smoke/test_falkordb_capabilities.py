"""FalkorDB capability and compatibility test suite."""

import uuid

import pytest

from backend.app.graph.client import FalkorDBClient
from backend.app.graph.initialization import initialize_schema
from backend.app.graph.schema import (
    LABEL_MODULE,
    REL_DEPENDS_ON,
    format_module_id,
)
from tests.fixtures.synthetic_graph import seed_synthetic_graph


@pytest.fixture(scope="module")
def client():
    """FalkorDB test client fixture."""
    cli = FalkorDBClient()
    assert cli.ping(), "FalkorDB must be running for compatibility tests"
    yield cli
    cli.close()


def test_1_connect_and_query(client: FalkorDBClient):
    """1. Connecting and issuing a supported graph query."""
    test_graph = f"test_conn_{uuid.uuid4().hex[:6]}"
    try:
        res = client.query("RETURN 42 AS answer", graph_name=test_graph)
        assert res is not None
        assert res[0][0] == 42
    finally:
        client.delete_graph(test_graph, force=True)


def test_2_idempotent_schema_and_seeding(client: FalkorDBClient):
    """2. Idempotent node and relationship initialization."""
    test_graph = f"test_idempotent_{uuid.uuid4().hex[:6]}"
    try:
        # First initialization
        res1 = initialize_schema(client, graph_name=test_graph)
        assert res1["status"] == "INITIALIZED"

        # Second initialization (must not fail or duplicate)
        res2 = initialize_schema(client, graph_name=test_graph)
        assert res2["status"] == "INITIALIZED"

        # Seed data
        seed_res = seed_synthetic_graph(client, graph_name=test_graph)
        assert seed_res["module_count"] == 5

        # Query module count
        mods = client.query("MATCH (m:Module) RETURN count(m)", graph_name=test_graph)
        assert mods[0][0] == 5
    finally:
        client.delete_graph(test_graph, force=True)


def test_3_and_4_graph_copy_and_isolation(client: FalkorDBClient):
    """3. GRAPH.COPY with unique temporary destination.
    4. Querying copied graph and confirming source graph remains unchanged."""
    source_graph = f"test_src_{uuid.uuid4().hex[:6]}"
    copy_graph = f"test_copy_{uuid.uuid4().hex[:6]}"

    try:
        seed_synthetic_graph(client, graph_name=source_graph)

        # Copy graph
        success = client.copy_graph(source_graph, copy_graph)
        assert success is True

        # Verify copy has same modules
        copy_mods = client.query("MATCH (m:Module) RETURN count(m)", graph_name=copy_graph)
        assert copy_mods[0][0] == 5

        # Add a node to copy only
        client.query("CREATE (:Module {id: 'mod:new_feature', name: 'new_feature'})", graph_name=copy_graph)
        assert client.query("MATCH (m:Module) RETURN count(m)", graph_name=copy_graph)[0][0] == 6

        # Source graph must remain unchanged with 5 modules
        assert client.query("MATCH (m:Module) RETURN count(m)", graph_name=source_graph)[0][0] == 5
    finally:
        client.delete_graph(source_graph, force=True)
        client.delete_graph(copy_graph, force=True)


def test_5_isolated_deletion_and_relationship_cleanup(client: FalkorDBClient):
    """5. Deleting a node in the copied graph and verifying connected relationships are removed."""
    source_graph = f"test_src_del_{uuid.uuid4().hex[:6]}"
    copy_graph = f"test_copy_del_{uuid.uuid4().hex[:6]}"

    try:
        seed_synthetic_graph(client, graph_name=source_graph)
        client.copy_graph(source_graph, copy_graph)

        # Delete database module in the copy
        db_id = format_module_id("pkg/database")
        del_query = f"""
        MATCH (m:{LABEL_MODULE} {{id: $id}})
        DETACH DELETE m
        """
        client.query(del_query, params={"id": db_id}, graph_name=copy_graph)

        # In copy: database module is gone
        res_copy = client.query("MATCH (m:Module {id: $id}) RETURN m", params={"id": db_id}, graph_name=copy_graph)
        assert len(res_copy) == 0

        # In copy: relationships to db are gone
        rels_copy = client.query(
            "MATCH ()-[r:DEPENDS_ON]->(m:Module {id: $id}) RETURN r",
            params={"id": db_id},
            graph_name=copy_graph,
        )
        assert len(rels_copy) == 0

        # In source: database module and relationships remain fully intact
        res_src = client.query("MATCH (m:Module {id: $id}) RETURN m", params={"id": db_id}, graph_name=source_graph)
        assert len(res_src) == 1
    finally:
        client.delete_graph(source_graph, force=True)
        client.delete_graph(copy_graph, force=True)


def test_6_pagerank_supported_signature(client: FalkorDBClient):
    """6. Calling PageRank using the exact procedure signature supported by the pinned release."""
    test_graph = f"test_pr_{uuid.uuid4().hex[:6]}"
    try:
        seed_synthetic_graph(client, graph_name=test_graph)

        # FalkorDB v4.4.1 supported procedure signature: CALL algo.pageRank('Module', 'DEPENDS_ON')
        pr_res = client.query(f"CALL algo.pageRank('{LABEL_MODULE}', '{REL_DEPENDS_ON}')", graph_name=test_graph)
        assert pr_res is not None
        assert len(pr_res) > 0

        # Check return format: each row is [Node, rank_score]
        for row in pr_res:
            node, score = row[0], row[1]
            assert hasattr(node, "properties")
            assert isinstance(score, float)
            assert score > 0.0
    finally:
        client.delete_graph(test_graph, force=True)


def test_7_shortest_path_and_betweenness_checks(client: FalkorDBClient):
    """7. Checking signatures for shortest-path and betweenness."""
    test_graph = f"test_sp_{uuid.uuid4().hex[:6]}"
    try:
        seed_synthetic_graph(client, graph_name=test_graph)

        # 1. Betweenness procedure check: record actual availability
        try:
            client.query("CALL algo.betweenness()", graph_name=test_graph)
            betweenness_supported = True
        except Exception:
            betweenness_supported = False
        assert betweenness_supported is False, (
            "Betweenness is not registered as a standalone procedure in FalkorDB v4.4.1"
        )

        # 2. ShortestPath verification via native Cypher
        src_id = format_module_id("api/gateway")
        tgt_id = format_module_id("pkg/database")
        sp_query = f"""
        MATCH (a:{LABEL_MODULE} {{id: $src}}), (b:{LABEL_MODULE} {{id: $tgt}})
        RETURN shortestPath((a)-[:{REL_DEPENDS_ON}*]->(b)) AS sp
        """
        sp_res = client.query(sp_query, params={"src": src_id, "tgt": tgt_id}, graph_name=test_graph)
        assert sp_res is not None
        assert len(sp_res) == 1
        path = sp_res[0][0]
        # In FalkorDB, Path object represents the shortest path found
        assert path is not None
    finally:
        client.delete_graph(test_graph, force=True)


def test_8_and_9_temporary_graph_lifecycle_and_cleanup(client: FalkorDBClient):
    """8. Deleting temporary scenario graph successfully.
    9. Cleaning up temporary graph after both successful and intentionally failed paths."""
    temp_graph = f"test_scenario_{uuid.uuid4().hex[:6]}"

    # Path A: Successful creation and cleanup
    client.query("CREATE (:Module {id: 'mod:temp'})", graph_name=temp_graph)
    assert client.delete_graph(temp_graph, force=True) is True

    # Path B: Intentionally failed query followed by robust cleanup
    temp_fail_graph = f"test_fail_{uuid.uuid4().hex[:6]}"
    try:
        client.query("CREATE (:Module {id: 'mod:fail'})", graph_name=temp_fail_graph)
        # Intentional syntax error
        with pytest.raises(Exception):
            client.query("INVALID CYPHER SYNTAX", graph_name=temp_fail_graph)
    finally:
        # Cleanup must still succeed
        assert client.delete_graph(temp_fail_graph, force=True) is True


def test_10_cleanup_cannot_delete_protected_main_graph(client: FalkorDBClient):
    """10. Confirming that cleanup cannot delete the primary protected graph."""
    with pytest.raises(ValueError, match="Safety violation: Cannot delete protected primary graph"):
        client.delete_graph("nexusact_main")

    with pytest.raises(ValueError, match="Safety violation: Cannot delete protected primary graph"):
        client.delete_graph("gaf_main")
