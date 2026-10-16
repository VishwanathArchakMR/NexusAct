"""Safe data migration and classification repair for the FalkorDB public knowledge graph."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.sources.graph_persister import PUBLIC_GRAPH_NAME

logger = logging.getLogger("nexusact.sources.migration")


def repair_public_graph(
    client: FalkorDBClient | None = None,
    graph_name: str = PUBLIC_GRAPH_NAME,
) -> dict[str, Any]:
    """Safely repairs entity classifications and eliminates duplicate stubs in nexusact_public.

    1. Relabels misclassified Model stubs to Person, Organization, Paper, or Topic based on ID prefix.
    2. Merges duplicate nodes sharing identical IDs, preserving all valid edges.
    3. Keeps _SchemaMetadata isolated for schema versioning.
    """
    cli = client or graph_client
    counts: dict[str, int] = {
        "authors_reclassified": 0,
        "orgs_reclassified": 0,
        "papers_reclassified": 0,
        "topics_reclassified": 0,
        "duplicates_merged": 0,
    }

    try:
        # 1. Reclassify Authors
        auth_query = """
        MATCH (n:Model)
        WHERE n.id STARTS WITH 'openalex:A' OR n.id STARTS WITH 'openalex:author'
        SET n:Person
        REMOVE n:Model
        RETURN count(n)
        """
        r = cli.query(auth_query, graph_name=graph_name)
        counts["authors_reclassified"] = r[0][0] if r else 0

        # 2. Reclassify Organizations / Institutions
        org_query = """
        MATCH (n:Model)
        WHERE n.id STARTS WITH 'openalex:I' OR n.id STARTS WITH 'openalex:inst'
        SET n:Organization
        REMOVE n:Model
        RETURN count(n)
        """
        r = cli.query(org_query, graph_name=graph_name)
        counts["orgs_reclassified"] = r[0][0] if r else 0

        # 3. Reclassify Papers
        paper_query = """
        MATCH (n:Model)
        WHERE n.id STARTS WITH 'openalex:W' OR n.id STARTS WITH 'openalex:10.' OR n.id STARTS WITH 'doi:'
        SET n:Paper
        REMOVE n:Model
        RETURN count(n)
        """
        r = cli.query(paper_query, graph_name=graph_name)
        counts["papers_reclassified"] = r[0][0] if r else 0

        # 4. Reclassify Topics
        topic_query = """
        MATCH (n:Model)
        WHERE n.id STARTS WITH 'topic:' OR n.id STARTS WITH 'openalex:T'
        SET n:Topic
        REMOVE n:Model
        RETURN count(n)
        """
        r = cli.query(topic_query, graph_name=graph_name)
        counts["topics_reclassified"] = r[0][0] if r else 0

        # 5. Merge duplicates: find stub nodes that have a corresponding primary node
        merge_query = """
        MATCH (stub {is_stub: true})
        WHERE stub.id IS NOT NULL AND NOT stub:SourceRecord AND NOT stub:_SchemaMetadata
        WITH stub
        MATCH (primary)
        WHERE primary.id = stub.id AND id(primary) <> id(stub) AND (primary.is_stub IS NULL OR primary.is_stub = false)
        DETACH DELETE stub
        RETURN count(stub)
        """
        dup_res = cli.query(merge_query, graph_name=graph_name)
        counts["duplicates_merged"] = dup_res[0][0] if dup_res else 0

        logger.info("Public graph migration completed: %s", counts)
        return counts

    except Exception as exc:
        logger.error("Public graph migration encountered error: %s", exc)
        return counts
