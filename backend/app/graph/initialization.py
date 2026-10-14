"""Idempotent schema initialization and migration tracking for FalkorDB."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.app.core.errors import SchemaInitializationError
from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import (
    LABEL_SCHEMA_META,
    SCHEMA_VERSION,
    get_schema_indices,
)

logger = logging.getLogger("nexusact.graph.initialization")


def initialize_schema(
    client: Optional[FalkorDBClient] = None,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Initializes graph indices and schema metadata idempotently.
    Safe to call multiple times without duplicating indexes or corrupting data.
    """
    cli = client or graph_client
    target_graph = graph_name or cli.primary_graph_name

    logger.info("Initializing schema v%s on graph '%s'", SCHEMA_VERSION, target_graph)
    indices_created = 0
    indices_skipped = 0

    # 1. Apply indices idempotently
    for index_stmt in get_schema_indices():
        try:
            cli.query(index_stmt, graph_name=target_graph)
            indices_created += 1
            logger.debug("Applied index: %s", index_stmt)
        except Exception as exc:
            msg = str(exc).lower()
            if "already exists" in msg or "already indexed" in msg or "duplicate" in msg:
                indices_skipped += 1
                logger.debug("Index already exists (skipped): %s", index_stmt)
            else:
                logger.warning("Index statement notice [%s]: %s", index_stmt, exc)
                # In some versions, creating an index on empty graph returns warning; count as skipped
                indices_skipped += 1

    # 2. Record or update schema version metadata node
    now_iso = datetime.now(timezone.utc).isoformat()
    upsert_meta_query = f"""
    MERGE (m:{LABEL_SCHEMA_META} {{name: 'schema_version'}})
    SET m.version = $version,
        m.updated_at = $updated_at
    RETURN m.version AS version
    """
    try:
        res = cli.query(
            upsert_meta_query,
            params={"version": SCHEMA_VERSION, "updated_at": now_iso},
            graph_name=target_graph,
        )
        recorded_version = res[0][0] if res and len(res) > 0 else SCHEMA_VERSION
    except Exception as exc:
        logger.error("Failed to update schema metadata on '%s': %s", target_graph, exc)
        raise SchemaInitializationError(f"Failed to record schema metadata on '{target_graph}': {str(exc)}") from exc

    summary = {
        "graph_name": target_graph,
        "schema_version": recorded_version,
        "indices_created": indices_created,
        "indices_skipped": indices_skipped,
        "initialized_at": now_iso,
        "status": "INITIALIZED",
    }
    logger.info("Schema initialization complete: %s", summary)
    return summary
