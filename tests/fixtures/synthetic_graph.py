"""Deterministic synthetic graph fixture for NexusAct testing.

Graph topology (canonical: dependent -[:DEPENDS_ON]-> dependency):
  gateway -> orders -> billing -> database
  gateway -> inventory -> database
  orders  -> database                (direct shortcut)

This creates TWO distinct paths from gateway to database:
  gateway->orders->billing->database   (3 hops)
  gateway->inventory->database         (2 hops)

When 'billing' is removed the inventory path to database SURVIVES,
proving the comparison is meaningful and not just detecting the deleted node.

Contributors:
  alice@nexus.test  — touches gateway, orders, billing  (more files, older)
  bob@nexus.test    — touches billing, database         (fewer files, recent)
  carol@nexus.test  — touches inventory only            (different module)

This ensures who_knows returns different scores for each candidate and
reviewer-history (REVIEWS edges) is available for bob and alice.
"""

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

# Stable timestamps (ISO-8601 UTC) – alice is older, bob is recent
_ALICE_COMMIT_TS = "2024-01-10T09:00:00+00:00"
_BOB_COMMIT_TS = "2025-09-01T14:00:00+00:00"
_CAROL_COMMIT_TS = "2025-06-15T11:00:00+00:00"


def seed_synthetic_graph(client: FalkorDBClient, graph_name: str = SYNTHETIC_TEST_GRAPH) -> Dict[str, Any]:
    """
    Seeds a deterministic synthetic repository graph in FalkorDB for testing.

    Modules  : gateway, orders, inventory, billing, database
    Edges    : gateway->orders, gateway->inventory, orders->billing,
               orders->database, inventory->database, billing->database
    Persons  : alice (old, many files), bob (recent, fewer), carol (inventory)
    Commits  : 3 commits with TOUCHES->File links so who_knows can score
    Reviews  : bob reviews billing+database; alice reviews gateway
    """
    # Always start fresh to guarantee deterministic state
    client.delete_graph(graph_name, force=True)

    # ── 1. Modules ──────────────────────────────────────────────────────────
    modules = [
        {"id": format_module_id("api/gateway"), "name": "gateway", "path": "src/api/gateway"},
        {"id": format_module_id("services/orders"), "name": "orders", "path": "src/services/orders"},
        {"id": format_module_id("services/inventory"), "name": "inventory", "path": "src/services/inventory"},
        {"id": format_module_id("services/billing"), "name": "billing", "path": "src/services/billing"},
        {"id": format_module_id("pkg/database"), "name": "database", "path": "src/pkg/database"},
    ]
    client.query(
        "UNWIND $modules AS m CREATE (mod:Module {id: m.id, name: m.name, path: m.path})",
        params={"modules": modules},
        graph_name=graph_name,
    )

    # ── 2. Files (one representative file per module) ────────────────────────
    files = [
        {"id": "file:src/api/gateway.py", "path": "src/api/gateway.py"},
        {"id": "file:src/services/orders.py", "path": "src/services/orders.py"},
        {"id": "file:src/services/inventory.py", "path": "src/services/inventory.py"},
        {"id": "file:src/services/billing.py", "path": "src/services/billing.py"},
        {"id": "file:src/pkg/database.py", "path": "src/pkg/database.py"},
    ]
    client.query(
        "UNWIND $files AS f CREATE (fl:File {id: f.id, path: f.path})",
        params={"files": files},
        graph_name=graph_name,
    )

    # Module -[:CONTAINS]-> File
    module_file_links = [
        (format_module_id("api/gateway"), "file:src/api/gateway.py"),
        (format_module_id("services/orders"), "file:src/services/orders.py"),
        (format_module_id("services/inventory"), "file:src/services/inventory.py"),
        (format_module_id("services/billing"), "file:src/services/billing.py"),
        (format_module_id("pkg/database"), "file:src/pkg/database.py"),
    ]
    for mod_id, file_id in module_file_links:
        client.query(
            "MATCH (m:Module {id: $mid}), (f:File {id: $fid}) CREATE (m)-[:CONTAINS]->(f)",
            params={"mid": mod_id, "fid": file_id},
            graph_name=graph_name,
        )

    # ── 3. Dependency edges ──────────────────────────────────────────────────
    # gateway -> orders -> billing -> database
    # gateway -> inventory -> database
    # orders  -> database (alternate route)
    dependencies = [
        ("api/gateway", "services/orders"),
        ("api/gateway", "services/inventory"),
        ("services/orders", "services/billing"),
        ("services/orders", "pkg/database"),  # shortcut: orders->database directly
        ("services/inventory", "pkg/database"),
        ("services/billing", "pkg/database"),
    ]
    for source, target in dependencies:
        client.query(
            f"""
            MATCH (src:{LABEL_MODULE} {{id: $src_id}}), (tgt:{LABEL_MODULE} {{id: $tgt_id}})
            CREATE (src)-[:{REL_DEPENDS_ON} {{source_file: $sf, evidence: 'observed'}}]->(tgt)
            """,
            params={
                "src_id": format_module_id(source),
                "tgt_id": format_module_id(target),
                "sf": f"src/{source}.py",
            },
            graph_name=graph_name,
        )

    # ── 4. Persons ───────────────────────────────────────────────────────────
    persons = [
        {"id": format_person_id("alice@nexus.test"), "name": "Alice Developer", "email": "alice@nexus.test"},
        {"id": format_person_id("bob@nexus.test"), "name": "Bob Architect", "email": "bob@nexus.test"},
        {"id": format_person_id("carol@nexus.test"), "name": "Carol Ops", "email": "carol@nexus.test"},
    ]
    client.query(
        "UNWIND $persons AS p CREATE (per:Person {id: p.id, name: p.name, email: p.email})",
        params={"persons": persons},
        graph_name=graph_name,
    )

    # ── 5. Commits with TOUCHES links ────────────────────────────────────────
    # commit-A: alice touches gateway, orders, billing (older, many files)
    # commit-B: bob touches billing, database (recent, fewer files)
    # commit-C: carol touches inventory
    commits = [
        {
            "id": "commit:aaa111",
            "hash": "aaa111",
            "msg": "feat: initial gateway and order flow",
            "ts": _ALICE_COMMIT_TS,
            "person_id": format_person_id("alice@nexus.test"),
            "files": [
                "file:src/api/gateway.py",
                "file:src/services/orders.py",
                "file:src/services/billing.py",
            ],
        },
        {
            "id": "commit:bbb222",
            "hash": "bbb222",
            "msg": "fix: billing DB connection handling",
            "ts": _BOB_COMMIT_TS,
            "person_id": format_person_id("bob@nexus.test"),
            "files": [
                "file:src/services/billing.py",
                "file:src/pkg/database.py",
            ],
        },
        {
            "id": "commit:ccc333",
            "hash": "ccc333",
            "msg": "feat: inventory service integration",
            "ts": _CAROL_COMMIT_TS,
            "person_id": format_person_id("carol@nexus.test"),
            "files": [
                "file:src/services/inventory.py",
            ],
        },
    ]

    for c in commits:
        client.query(
            "CREATE (cm:Commit {id: $id, hash: $hash, timestamp: $ts, message: $msg})",
            params={"id": c["id"], "hash": c["hash"], "ts": c["ts"], "msg": c["msg"]},
            graph_name=graph_name,
        )
        client.query(
            "MATCH (p:Person {id: $pid}), (cm:Commit {id: $cid}) CREATE (p)-[:AUTHORED]->(cm)",
            params={"pid": c["person_id"], "cid": c["id"]},
            graph_name=graph_name,
        )
        for fid in c["files"]:
            client.query(
                "MATCH (cm:Commit {id: $cid}), (f:File {id: $fid}) CREATE (cm)-[:TOUCHES]->(f)",
                params={"cid": c["id"], "fid": fid},
                graph_name=graph_name,
            )

    # ── 6. REVIEWS edges (explicit designated reviewer history) ──────────────
    review_links = [
        ("alice@nexus.test", "api/gateway"),
        ("bob@nexus.test", "pkg/database"),
        ("bob@nexus.test", "services/billing"),
        ("carol@nexus.test", "services/inventory"),
    ]
    for email, mod_name in review_links:
        client.query(
            f"""
            MATCH (p:{LABEL_PERSON} {{id: $person_id}}), (m:{LABEL_MODULE} {{id: $mod_id}})
            CREATE (p)-[:{REL_REVIEWS}]->(m)
            """,
            params={
                "person_id": format_person_id(email),
                "mod_id": format_module_id(mod_name),
            },
            graph_name=graph_name,
        )

    return {
        "graph_name": graph_name,
        "module_count": len(modules),
        "file_count": len(files),
        "dependency_count": len(dependencies),
        "person_count": len(persons),
        "commit_count": len(commits),
        "review_count": len(review_links),
    }


def teardown_synthetic_graph(client: FalkorDBClient, graph_name: str = SYNTHETIC_TEST_GRAPH) -> bool:
    """Safely cleans up the synthetic fixture graph."""
    return client.delete_graph(graph_name, force=True)
