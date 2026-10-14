"""Deterministic synthetic graph fixture for NexusAct testing."""

from typing import Any, Dict

from backend.app.graph.client import FalkorDBClient
from backend.app.graph.schema import (
    LABEL_MODULE,
    LABEL_PERSON,
    REL_DEPENDS_ON,
    REL_REVIEWS,
    format_module_id,
    format_person_id,
)

SYNTHETIC_TEST_GRAPH = "nexusact_test_synthetic"


def seed_synthetic_graph(client: FalkorDBClient, graph_name: str = SYNTHETIC_TEST_GRAPH) -> Dict[str, Any]:
    """
    Seeds a deterministic synthetic repository graph in FalkorDB for testing.
    Graph topology:
      gateway -> orders -> billing -> db
      gateway -> inventory -> db
    """
    # Ensure fresh graph
    client.delete_graph(graph_name, force=True)

    # 1. Create Modules
    modules = [
        {"id": format_module_id("api/gateway"), "name": "gateway", "path": "src/gateway"},
        {"id": format_module_id("services/orders"), "name": "orders", "path": "src/orders"},
        {
            "id": format_module_id("services/inventory"),
            "name": "inventory",
            "path": "src/inventory",
        },
        {"id": format_module_id("services/billing"), "name": "billing", "path": "src/billing"},
        {"id": format_module_id("pkg/database"), "name": "database", "path": "pkg/database"},
    ]

    create_modules_query = """
    UNWIND $modules AS m
    CREATE (mod:Module {id: m.id, name: m.name, path: m.path})
    """
    client.query(create_modules_query, params={"modules": modules}, graph_name=graph_name)

    # 2. Create Dependencies (Canonical: DependentModule -> DEPENDS_ON -> DependencyModule)
    dependencies = [
        ("api/gateway", "services/orders"),
        ("api/gateway", "services/inventory"),
        ("services/orders", "services/billing"),
        ("services/orders", "pkg/database"),
        ("services/inventory", "pkg/database"),
        ("services/billing", "pkg/database"),
    ]

    for source, target in dependencies:
        dep_query = f"""
        MATCH (src:{LABEL_MODULE} {{id: $src_id}}), (tgt:{LABEL_MODULE} {{id: $tgt_id}})
        CREATE (src)-[:{REL_DEPENDS_ON}]->(tgt)
        """
        client.query(
            dep_query,
            params={
                "src_id": format_module_id(source),
                "tgt_id": format_module_id(target),
            },
            graph_name=graph_name,
        )

    # 3. Create Developers / Persons
    persons = [
        {
            "id": format_person_id("alice@nexus.test"),
            "name": "Alice Developer",
            "email": "alice@nexus.test",
        },
        {
            "id": format_person_id("bob@nexus.test"),
            "name": "Bob Architect",
            "email": "bob@nexus.test",
        },
        {
            "id": format_person_id("carol@nexus.test"),
            "name": "Carol Ops",
            "email": "carol@nexus.test",
        },
    ]

    create_persons_query = """
    UNWIND $persons AS p
    CREATE (per:Person {id: p.id, name: p.name, email: p.email})
    """
    client.query(create_persons_query, params={"persons": persons}, graph_name=graph_name)

    # 4. Link Reviews
    review_links = [
        ("alice@nexus.test", "api/gateway"),
        ("bob@nexus.test", "pkg/database"),
        ("bob@nexus.test", "services/billing"),
        ("carol@nexus.test", "services/inventory"),
    ]

    for email, mod_name in review_links:
        rev_query = f"""
        MATCH (p:{LABEL_PERSON} {{id: $person_id}}), (m:{LABEL_MODULE} {{id: $mod_id}})
        CREATE (p)-[:{REL_REVIEWS}]->(m)
        """
        client.query(
            rev_query,
            params={
                "person_id": format_person_id(email),
                "mod_id": format_module_id(mod_name),
            },
            graph_name=graph_name,
        )

    return {
        "graph_name": graph_name,
        "module_count": len(modules),
        "dependency_count": len(dependencies),
        "person_count": len(persons),
        "review_count": len(review_links),
    }


def teardown_synthetic_graph(client: FalkorDBClient, graph_name: str = SYNTHETIC_TEST_GRAPH) -> bool:
    """Safely cleans up the synthetic fixture graph."""
    return client.delete_graph(graph_name, force=True)
