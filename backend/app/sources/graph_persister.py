"""FalkorDB persistence for universal public-data entities, evidence, and relationships."""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.initialization import initialize_schema
from backend.app.graph.schema import (
    LABEL_DATASET,
    LABEL_MODEL,
    LABEL_ORGANIZATION,
    LABEL_PAPER,
    LABEL_PERSON,
    LABEL_SOURCE_RECORD,
    LABEL_TOPIC,
)
from backend.app.sources.connector_registry import SourceRecord

logger = logging.getLogger("nexusact.sources.graph_persister")

PUBLIC_GRAPH_NAME = "nexusact_public"


class PublicGraphPersister:
    """Manages idempotent upserts of public data records into FalkorDB."""

    def __init__(self, client: FalkorDBClient | None = None, graph_name: str = PUBLIC_GRAPH_NAME) -> None:
        self.client = client or graph_client
        self.graph_name = graph_name
        self._schema_initialized = False

    def ensure_schema(self) -> None:
        """Initializes schema and indices on the public graph idempotently."""
        if not self._schema_initialized:
            try:
                initialize_schema(client=self.client, graph_name=self.graph_name)
                self._schema_initialized = True
            except Exception as exc:
                logger.warning("Failed ensuring schema on '%s': %s", self.graph_name, exc)

    def persist_records(self, records: list[SourceRecord]) -> dict[str, int]:
        """Idempotently upserts source records, entities, and relationships into FalkorDB."""
        self.ensure_schema()
        counts = {"entities": 0, "source_records": 0, "relationships": 0}

        for record in records:
            try:
                # 1. Upsert SourceRecord metadata node
                sr_id = f"sr:{record.source_id}:{record.external_id}"
                sr_query = f"""
                MERGE (sr:{LABEL_SOURCE_RECORD} {{id: $sr_id}})
                SET sr.source_id = $source_id,
                    sr.external_id = $external_id,
                    sr.canonical_url = $canonical_url,
                    sr.retrieved_at = $retrieved_at,
                    sr.raw_hash = $raw_hash
                RETURN sr.id
                """
                self.client.query(
                    sr_query,
                    params={
                        "sr_id": sr_id,
                        "source_id": record.source_id,
                        "external_id": record.external_id,
                        "canonical_url": record.canonical_url,
                        "retrieved_at": record.retrieved_at,
                        "raw_hash": record.raw_hash,
                    },
                    graph_name=self.graph_name,
                )
                counts["source_records"] += 1

                # 2. Upsert Primary Entity Node
                entity_node_id = f"{record.source_id}:{record.external_id}"
                self._upsert_entity_node(record.entity_type, entity_node_id, record.data)
                counts["entities"] += 1

                # 3. Link Entity -> SUPPORTED_BY -> SourceRecord
                link_query = f"""
                MATCH (e {{id: $entity_id}}), (sr:{LABEL_SOURCE_RECORD} {{id: $sr_id}})
                MERGE (e)-[r:SUPPORTED_BY]->(sr)
                RETURN count(r)
                """
                self.client.query(
                    link_query,
                    params={"entity_id": entity_node_id, "sr_id": sr_id},
                    graph_name=self.graph_name,
                )

                # 4. Upsert relationships
                for rel in record.relationships:
                    # Semantic label hints from relationship type
                    src_hint = None
                    tgt_hint = None
                    if rel.relation_type == "AUTHORED":
                        src_hint = "Person"
                        tgt_hint = "Paper"
                    elif rel.relation_type == "AFFILIATED_WITH":
                        src_hint = "Person"
                        tgt_hint = "Organization"
                    elif rel.relation_type == "CITES":
                        src_hint = "Paper"
                        tgt_hint = "Paper"
                    elif rel.relation_type == "USES_DATASET":
                        src_hint = "Model"
                        tgt_hint = "Dataset"
                    elif rel.relation_type == "HAS_TOPIC":
                        src_hint = "Paper"
                        tgt_hint = "Topic"

                    self._ensure_stub_node(rel.target_entity_id, label_hint=tgt_hint)
                    self._ensure_stub_node(rel.source_entity_id, label_hint=src_hint)

                    rel_query = f"""
                    MATCH (s {{id: $source_id}}), (t {{id: $target_id}})
                    MERGE (s)-[r:{rel.relation_type}]->(t)
                    SET r.confidence = $confidence,
                        r.evidence_field = $evidence_field,
                        r.provenance_url = $provenance_url
                    RETURN count(r)
                    """
                    self.client.query(
                        rel_query,
                        params={
                            "source_id": rel.source_entity_id,
                            "target_id": rel.target_entity_id,
                            "confidence": rel.confidence,
                            "evidence_field": rel.evidence_field,
                            "provenance_url": rel.provenance_url,
                        },
                        graph_name=self.graph_name,
                    )
                    counts["relationships"] += 1

            except Exception as exc:
                logger.error("Failed persisting record '%s': %s", record.external_id, exc)

        return counts

    def _upsert_entity_node(self, entity_type: str, node_id: str, data: dict[str, Any]) -> None:
        """Upserts an entity node with its specific label and properties."""
        label = self._normalize_label(entity_type)
        name = data.get("title") or data.get("name") or node_id

        query = f"""
        MERGE (n {{id: $node_id}})
        SET n:{label},
            n.name = $name,
            n.label = $name
        """
        params: dict[str, Any] = {"node_id": node_id, "name": name}

        # Add optional properties safely
        if "doi" in data and data["doi"]:
            query += ", n.doi = $doi"
            params["doi"] = data["doi"]
        if "publication_year" in data and data["publication_year"]:
            query += ", n.publication_year = $year"
            params["year"] = data["publication_year"]
        if "author" in data and data["author"]:
            query += ", n.author = $author"
            params["author"] = data["author"]
        if "pipeline_tag" in data and data["pipeline_tag"]:
            query += ", n.pipeline_tag = $pipeline_tag"
            params["pipeline_tag"] = data["pipeline_tag"]
        if "downloads" in data:
            query += ", n.downloads = $downloads"
            params["downloads"] = data["downloads"]
        if "description" in data and data["description"]:
            query += ", n.description = $description"
            params["description"] = data["description"]

        query += " RETURN n.id"
        self.client.query(query, params=params, graph_name=self.graph_name)

    def _ensure_stub_node(self, node_id: str, label_hint: str | None = None) -> None:
        """Ensures that a node with the given ID exists so that relationships can bind to it."""
        label = self._normalize_label(label_hint) if label_hint else self._infer_label_from_id(node_id)
        query = f"""
        MERGE (n {{id: $node_id}})
        ON CREATE SET n:{label}, n.name = $node_id, n.label = $node_id, n.is_stub = true
        """
        self.client.query(query, params={"node_id": node_id}, graph_name=self.graph_name)

    def _normalize_label(self, entity_type: str) -> str:
        mapping = {
            "model": LABEL_MODEL,
            "dataset": LABEL_DATASET,
            "paper": LABEL_PAPER,
            "organization": LABEL_ORGANIZATION,
            "person": LABEL_PERSON,
            "topic": LABEL_TOPIC,
        }
        return mapping.get(entity_type.lower(), LABEL_MODEL)

    def _infer_label_from_id(self, node_id: str) -> str:
        clean = node_id.strip()
        parts = clean.split(":")
        prefix = parts[0].lower() if parts else ""
        sub = parts[1] if len(parts) > 1 else ""

        if prefix in ("org", "institution"):
            return LABEL_ORGANIZATION
        if prefix in ("person", "author"):
            return LABEL_PERSON
        if prefix in ("paper", "crossref", "doi"):
            return LABEL_PAPER
        if prefix in ("topic",):
            return LABEL_TOPIC
        if prefix in ("dataset",):
            return LABEL_DATASET
        if prefix in ("model",):
            return LABEL_MODEL

        # OpenAlex IDs: A (author), I (institution), W (work/paper), T (topic)
        if prefix == "openalex":
            if sub.startswith("A") or sub.startswith("author"):
                return LABEL_PERSON
            elif sub.startswith("I") or sub.startswith("inst"):
                return LABEL_ORGANIZATION
            elif sub.startswith("W") or "/" in sub or sub.startswith("10."):
                return LABEL_PAPER
            elif sub.startswith("T"):
                return LABEL_TOPIC

        if prefix == "doi" or clean.startswith("10."):
            return LABEL_PAPER

        if prefix == "hf":
            if sub.startswith("dataset") or "dataset" in sub:
                return LABEL_DATASET
            return LABEL_MODEL

        return LABEL_MODEL

    def get_subgraph(self, limit: int = 50) -> dict[str, Any]:
        """Returns nodes and edges from the public knowledge graph for frontend visualization."""
        self.ensure_schema()
        nodes_query = f"""
        MATCH (n)
        WHERE NOT n:{LABEL_SOURCE_RECORD}
          AND NOT n:_SchemaMetadata
          AND NOT n:SchemaMetadata
          AND NOT n:Investigation
          AND NOT n:ToolInvocation
        RETURN DISTINCT n.id AS id, labels(n)[0] AS type, coalesce(n.name, n.id) AS label, properties(n) AS props
        LIMIT {limit}
        """
        edges_query = f"""
        MATCH (s)-[r]->(t)
        WHERE NOT s:{LABEL_SOURCE_RECORD} AND NOT t:{LABEL_SOURCE_RECORD}
          AND NOT s:_SchemaMetadata AND NOT t:_SchemaMetadata
          AND NOT s:SchemaMetadata AND NOT t:SchemaMetadata
          AND NOT s:Investigation AND NOT t:Investigation
          AND NOT s:ToolInvocation AND NOT t:ToolInvocation
        RETURN DISTINCT s.id AS source, t.id AS target, type(r) AS type, properties(r) AS props
        LIMIT {limit * 2}
        """

        try:
            node_rows = self.client.query(nodes_query, graph_name=self.graph_name)
            edge_rows = self.client.query(edges_query, graph_name=self.graph_name)

            seen_nodes: set[str] = set()
            nodes = []
            for r in node_rows:
                node_id = str(r[0])
                if node_id not in seen_nodes:
                    seen_nodes.add(node_id)
                    nodes.append({"id": node_id, "type": r[1], "label": r[2], "properties": r[3] if len(r) > 3 else {}})

            edges = [
                {"source": r[0], "target": r[1], "type": r[2], "properties": r[3] if len(r) > 3 else {}}
                for r in edge_rows
            ]
            return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}
        except Exception as exc:
            logger.warning("Failed querying subgraph on '%s': %s", self.graph_name, exc)
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}

    def find_path(self, start_id: str, target_id: str, max_hops: int = 3) -> list[dict[str, Any]]:
        """Finds paths between two public entities with evidence details."""
        self.ensure_schema()
        hops = min(max(1, max_hops), 4)
        query = f"""
        MATCH p = (s {{id: $start_id}})-[*1..{hops}]-(t {{id: $target_id}})
        RETURN [node in nodes(p) | {{
                   id: node.id,
                   label: coalesce(node.name, node.id),
                   type: labels(node)[0]
               }}] AS path_nodes,
               [rel in relationships(p) | {{
                   type: type(rel),
                   confidence: rel.confidence,
                   evidence: rel.evidence_field,
                   provenance: rel.provenance_url
               }}] AS path_rels
        LIMIT 5
        """
        try:
            res = self.client.query(
                query, params={"start_id": start_id, "target_id": target_id}, graph_name=self.graph_name
            )
            paths = []
            for row in res:
                paths.append({"nodes": row[0], "relationships": row[1]})
            return paths
        except Exception as exc:
            logger.warning("Path query failed: %s", exc)
            return []

    def save_investigation(
        self,
        investigation_id: str,
        question: str,
        summary: str,
        approach: str,
        sources: list[str],
        entities: list[dict[str, Any]],
        next_action: dict[str, Any] | None = None,
        input_mode: str = "public",
        repository_id: str | None = None,
        graph_name: str | None = None,
        commit_sha: str | None = None,
    ) -> bool:
        """Persists a completed investigation into FalkorDB as persistent memory."""
        self.ensure_schema()
        sources_str = ",".join(sources) if sources else ""
        act_id = next_action.get("id", "") if next_action else ""
        act_title = next_action.get("title", "") if next_action else ""
        act_desc = next_action.get("description", "") if next_action else ""
        act_status = next_action.get("status", "PROPOSED") if next_action else "PROPOSED"

        query = """
        MERGE (inv:PublicInvestigation {id: $inv_id})
        SET inv.question = $question,
            inv.summary = $summary,
            inv.approach = $approach,
            inv.sources = $sources,
            inv.action_id = $act_id,
            inv.action_title = $act_title,
            inv.action_desc = $act_desc,
            inv.action_status = $act_status,
            inv.input_mode = $input_mode,
            inv.repository_id = $repo_id,
            inv.graph_name = $graph_name,
            inv.commit_sha = $commit_sha,
            inv.created_at = coalesce(inv.created_at, $created_at)
        RETURN inv.id
        """
        try:
            self.client.query(
                query,
                params={
                    "inv_id": investigation_id,
                    "question": question,
                    "summary": summary,
                    "approach": approach,
                    "sources": sources_str,
                    "act_id": act_id,
                    "act_title": act_title,
                    "act_desc": act_desc,
                    "act_status": act_status,
                    "input_mode": input_mode,
                    "repo_id": repository_id or "",
                    "graph_name": graph_name or "",
                    "commit_sha": commit_sha or "",
                    "created_at": time.time(),
                },
                graph_name=self.graph_name,
            )

            # Link investigation -> investigated entities
            for ent in entities[:10]:
                ent_id = ent.get("id")
                if ent_id:
                    self.client.query(
                        """
                        MATCH (inv:PublicInvestigation {id: $inv_id}), (e {id: $ent_id})
                        MERGE (inv)-[:INVESTIGATED_ENTITY]->(e)
                        """,
                        params={"inv_id": investigation_id, "ent_id": ent_id},
                        graph_name=self.graph_name,
                    )
            return True
        except Exception as exc:
            logger.warning("Failed saving investigation memory '%s': %s", investigation_id, exc)
            return False

    def list_saved_investigations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieves past investigations from FalkorDB graph memory."""
        self.ensure_schema()
        query = """
        MATCH (inv:PublicInvestigation)
        RETURN inv.id, inv.question, inv.summary, inv.sources, inv.approach,
               inv.action_id, inv.action_title, inv.action_desc, inv.action_status,
               coalesce(inv.created_at, 0.0) AS created_at,
               coalesce(inv.input_mode, 'public') AS input_mode,
               coalesce(inv.repository_id, '') AS repository_id,
               coalesce(inv.graph_name, '') AS graph_name,
               coalesce(inv.commit_sha, '') AS commit_sha
        ORDER BY created_at DESC
        LIMIT $limit
        """
        try:
            rows = self.client.query(query, params={"limit": limit}, graph_name=self.graph_name)
            results = []
            for r in rows:
                results.append(
                    {
                        "investigation_id": r[0],
                        "question": r[1],
                        "summary": r[2],
                        "sources": r[3],
                        "approach": r[4],
                        "action_id": r[5],
                        "action_title": r[6],
                        "action_desc": r[7],
                        "action_status": r[8] or "PROPOSED",
                        "created_at": r[9],
                        "input_mode": r[10],
                        "repository_id": r[11] or None,
                        "graph_name": r[12] or None,
                        "commit_sha": r[13] or None,
                    }
                )
            return results
        except Exception as exc:
            logger.warning("Failed listing saved investigations: %s", exc)
            return []

    def confirm_action(self, action_id: str) -> bool:
        """Confirms and executes a proposed investigation action in the graph."""
        query = """
        MATCH (inv:PublicInvestigation {action_id: $action_id})
        SET inv.action_status = 'CONFIRMED'
        RETURN inv.id
        """
        try:
            rows = self.client.query(query, params={"action_id": action_id}, graph_name=self.graph_name)
            return len(rows) > 0
        except Exception as exc:
            logger.warning("Failed confirming action '%s': %s", action_id, exc)
            return False
