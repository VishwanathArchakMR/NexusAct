"""Safely seed a clearly synthetic graph for a public demo.

Only runs when the primary graph has no Module nodes. It never deletes a graph,
and it never imports or overwrites the developer's local graph.
"""

from typing import Any, Dict, Optional

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import format_file_id, format_module_id, format_person_id

DEMO_REPOSITORY_ID = "repo:nexusact-synthetic-public-demo"
DEMO_REPOSITORY_NAME = "NexusAct Synthetic Demo (fictional topology)"


def seed_public_demo_graph(client: Optional[FalkorDBClient] = None) -> Dict[str, Any]:
    """Seed a tiny dependency graph only if the target graph has no modules."""
    cli = client or graph_client
    existing = cli.query("MATCH (m:Module) RETURN count(m) AS count")
    module_count = int(existing[0][0]) if existing else 0
    if module_count:
        return {
            "status": "SKIPPED_EXISTING_DATA",
            "reason": "primary graph already contains Module nodes",
            "module_count": module_count,
        }

    cli.query(
        """
        MERGE (r:Repository {id: $id})
        SET r.name = $name,
            r.path = 'synthetic://nexusact-public-demo',
            r.source_type = 'synthetic_demo',
            r.synthetic = true,
            r.description = 'Fictional sample topology for graph reasoning; not a real repository.'
        """,
        params={"id": DEMO_REPOSITORY_ID, "name": DEMO_REPOSITORY_NAME},
    )

    module_specs = [
        ("api/gateway", "gateway", "src/api/gateway.py"),
        ("services/orders", "orders", "src/services/orders.py"),
        ("services/inventory", "inventory", "src/services/inventory.py"),
        ("services/billing", "billing", "src/services/billing.py"),
        ("pkg/database", "database", "src/pkg/database.py"),
    ]
    modules = [
        {
            "id": format_module_id(module_path),
            "name": name,
            "path": path,
            "repo_id": DEMO_REPOSITORY_ID,
        }
        for module_path, name, path in module_specs
    ]
    cli.query(
        """
        UNWIND $items AS item
        MERGE (m:Module {id: item.id})
        SET m.name = item.name, m.path = item.path,
            m.repository_id = item.repo_id,
            m.source_type = 'synthetic_demo', m.synthetic = true
        WITH m, item
        MATCH (r:Repository {id: item.repo_id})
        MERGE (r)-[:CONTAINS]->(m)
        """,
        params={"items": modules},
    )

    files_data = [
        {"id": format_file_id(path), "path": path, "module_id": format_module_id(module_path)}
        for module_path, _, path in module_specs
    ]
    cli.query(
        """
        UNWIND $items AS item
        MERGE (f:File {id: item.id})
        SET f.path = item.path, f.source_type = 'synthetic_demo', f.synthetic = true
        WITH f, item
        MATCH (m:Module {id: item.module_id})
        MERGE (m)-[:CONTAINS]->(f)
        """,
        params={"items": files_data},
    )

    edges = [
        ("api/gateway", "services/orders", "src/api/gateway.py"),
        ("api/gateway", "services/inventory", "src/api/gateway.py"),
        ("services/orders", "services/billing", "src/services/orders.py"),
        ("services/orders", "pkg/database", "src/services/orders.py"),
        ("services/inventory", "pkg/database", "src/services/inventory.py"),
        ("services/billing", "pkg/database", "src/services/billing.py"),
    ]
    cli.query(
        """
        UNWIND $items AS item
        MATCH (a:Module {id: item.source_id}), (b:Module {id: item.target_id})
        MERGE (a)-[rel:DEPENDS_ON {source_file: item.source_file}]->(b)
        SET rel.evidence = 'synthetic_demo'
        """,
        params={
            "items": [
                {
                    "source_id": format_module_id(a),
                    "target_id": format_module_id(b),
                    "source_file": source_file,
                }
                for a, b, source_file in edges
            ]
        },
    )

    people = [
        {"id": format_person_id("alex@nexus.test"), "name": "Alex Developer", "email": "alex@nexus.test"},
        {"id": format_person_id("blake@nexus.test"), "name": "Blake Architect", "email": "blake@nexus.test"},
        {"id": format_person_id("casey@nexus.test"), "name": "Casey Engineer", "email": "casey@nexus.test"},
    ]
    cli.query(
        """
        UNWIND $items AS item
        MERGE (p:Person {id: item.id})
        SET p.name = item.name, p.email = item.email,
            p.source_type = 'synthetic_demo', p.synthetic = true
        """,
        params={"items": people},
    )

    commits = [
        ("synthetic-demo-001", "SYNTHETIC DEMO: gateway and order path", "2024-01-10T09:00:00+00:00", 0, [0, 1, 3]),
        ("synthetic-demo-002", "SYNTHETIC DEMO: billing database fix", "2025-09-01T14:00:00+00:00", 1, [3, 4]),
        ("synthetic-demo-003", "SYNTHETIC DEMO: inventory integration", "2025-06-15T11:00:00+00:00", 2, [2]),
    ]
    for commit_id, message, timestamp, author_idx, file_indices in commits:
        cid = f"commit:{commit_id}"
        cli.query(
            """
            MERGE (c:Commit {id: $id})
            SET c.hash = $hash, c.message = $message, c.timestamp = $timestamp,
                c.source_type = 'synthetic_demo', c.synthetic = true
            """,
            params={"id": cid, "hash": commit_id, "message": message, "timestamp": timestamp},
        )
        cli.query(
            "MATCH (p:Person {id: $pid}), (c:Commit {id: $cid}) MERGE (p)-[:AUTHORED]->(c)",
            params={"pid": people[author_idx]["id"], "cid": cid},
        )
        for file_idx in file_indices:
            cli.query(
                "MATCH (c:Commit {id: $cid}), (f:File {id: $fid}) MERGE (c)-[:TOUCHES]->(f)",
                params={"cid": cid, "fid": files_data[file_idx]["id"]},
            )

    reviews = [
        (0, "api/gateway"),
        (1, "pkg/database"),
        (1, "services/billing"),
        (2, "services/inventory"),
    ]
    for person_idx, module_path in reviews:
        cli.query(
            "MATCH (p:Person {id: $pid}), (m:Module {id: $mid}) MERGE (p)-[:REVIEWS]->(m)",
            params={"pid": people[person_idx]["id"], "mid": format_module_id(module_path)},
        )

    return {
        "status": "SEEDED_SYNTHETIC_DEMO",
        "repository": DEMO_REPOSITORY_NAME,
        "modules": len(modules),
        "files": len(files_data),
        "people": len(people),
        "commits": len(commits),
        "dependency_edges": len(edges),
    }
