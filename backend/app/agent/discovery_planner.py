"""Universal Discovery Planner and Execution Loop for Public Knowledge Graph Investigations."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend.app.sources.connector_registry import (
    ConnectorQuery,
    ConnectorRegistry,
    SourceRecord,
)
from backend.app.sources.graph_persister import PublicGraphPersister

logger = logging.getLogger("nexusact.agent.discovery_planner")


class UniversalInvestigationPlan(BaseModel):
    """Structured, bounded plan for public-data graph investigation."""

    plan_id: str = Field(default_factory=lambda: f"uplan_{uuid.uuid4().hex[:8]}")
    question: str
    target_entity_types: list[str] = Field(default_factory=list)
    relationship_focus: list[str] = Field(default_factory=list)
    selected_source_ids: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    max_results_per_source: int = 5
    traversal_depth: int = 2
    is_heuristic_fallback: bool = True


class UniversalInvestigationResult(BaseModel):
    """Complete, evidence-backed result of a public-data investigation."""

    investigation_id: str = Field(default_factory=lambda: f"uinv_{uuid.uuid4().hex[:8]}")
    question: str
    plan: UniversalInvestigationPlan
    sources_queried: dict[str, dict[str, Any]] = Field(default_factory=dict)
    records_ingested: int = 0
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    summary: str = ""
    coverage_limitations: list[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0


class UniversalDiscoveryPlanner:
    """Plans and executes bounded investigations across public data sources."""

    def __init__(self, persister: PublicGraphPersister | None = None) -> None:
        self.persister = persister or PublicGraphPersister()

    def create_plan(self, question: str) -> UniversalInvestigationPlan:
        """Parses natural-language question into a typed investigation plan."""
        q_lower = question.lower()

        target_entities: list[str] = []
        rel_focus: list[str] = []
        selected_sources: set[str] = set()

        # Entity detection
        if any(w in q_lower for w in ("model", "llm", "checkpoint", "transformer")):
            target_entities.append("Model")
            selected_sources.add("huggingface")
            selected_sources.add("wikidata")

        if any(w in q_lower for w in ("dataset", "corpus", "benchmark")):
            target_entities.append("Dataset")
            selected_sources.add("huggingface")

        if any(w in q_lower for w in ("paper", "publication", "article", "citation", "cites", "arxiv")):
            target_entities.append("Paper")
            selected_sources.add("openalex")
            selected_sources.add("crossref")

        if any(w in q_lower for w in ("organization", "institution", "company", "lab", "university", "publish")):
            target_entities.append("Organization")
            selected_sources.add("openalex")
            selected_sources.add("wikidata")

        if any(w in q_lower for w in ("author", "person", "researcher", "scientist", "who")):
            target_entities.append("Person")
            selected_sources.add("openalex")
            selected_sources.add("crossref")

        # Broad ecosystem query fallback (e.g. "map the open-source ai ecosystem")
        if not target_entities or any(w in q_lower for w in ("ecosystem", "map", "connect", "overview", "all")):
            target_entities = ["Model", "Dataset", "Paper", "Organization"]
            selected_sources.update(["huggingface", "openalex", "crossref", "wikidata"])

        # Extract search keywords: remove stop words
        stop_words = {
            "what",
            "which",
            "how",
            "who",
            "where",
            "are",
            "is",
            "the",
            "and",
            "or",
            "to",
            "in",
            "show",
            "find",
            "map",
            "connect",
            "connected",
            "between",
            "this",
            "these",
            "for",
            "of",
            "ecosystem",
            "open-source",
            "ai",
            "model",
            "models",
            "dataset",
            "datasets",
            "paper",
            "papers",
            "organization",
            "organizations",
            "publish",
            "publishes",
            "published",
            "related",
            "research",
            "concept",
            "concepts",
            "used",
            "train",
            "evaluate",
            "show",
            "explicitly",
            "reference",
            "references",
            "behind",
        }
        words = re.findall(r"[A-Za-z0-9_-]+", q_lower)
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # If all keywords removed, fallback to main concept or "artificial intelligence"
        search_term = " ".join(keywords[:3]) if keywords else "transformer"

        return UniversalInvestigationPlan(
            question=question,
            target_entity_types=target_entities,
            relationship_focus=rel_focus or ["USES_DATASET", "AUTHORED", "CITES", "AFFILIATED_WITH"],
            selected_source_ids=list(selected_sources),
            search_keywords=[search_term],
            max_results_per_source=5,
            traversal_depth=2,
            is_heuristic_fallback=True,
        )

    def execute_investigation(
        self,
        question: str,
        plan_override: UniversalInvestigationPlan | None = None,
    ) -> UniversalInvestigationResult:
        """Executes the investigation plan: queries sources, persists records, analyzes paths."""
        start_ts = time.monotonic()
        plan = plan_override or self.create_plan(question)

        all_records: list[SourceRecord] = []
        sources_status: dict[str, dict[str, Any]] = {}
        limitations: list[str] = []

        # 1. Fetch bounded records from selected connectors
        for source_id in plan.selected_source_ids:
            connector = ConnectorRegistry.get(source_id)
            if not connector:
                limitations.append(f"Connector '{source_id}' is not registered or unavailable.")
                continue

            query = ConnectorQuery(
                query_text=plan.search_keywords[0] if plan.search_keywords else "machine learning",
                entity_types=plan.target_entity_types,
                max_results=plan.max_results_per_source,
            )

            try:
                res = connector.search(query)
                sources_status[source_id] = {
                    "source_id": source_id,
                    "records_fetched": len(res.records),
                    "error": res.error,
                    "coverage_notes": res.coverage_notes,
                }
                all_records.extend(res.records)
                if res.coverage_notes:
                    limitations.extend(res.coverage_notes)
            except Exception as exc:
                sources_status[source_id] = {
                    "source_id": source_id,
                    "records_fetched": 0,
                    "error": str(exc),
                    "coverage_notes": [f"Source failed during search: {exc}"],
                }
                limitations.append(f"Source '{source_id}' failed: {exc}")

        # 2. Persist records into FalkorDB public graph
        persist_counts = self.persister.persist_records(all_records)

        # 3. Discover multi-hop paths if we have at least 2 entities
        discovered_paths: list[dict[str, Any]] = []
        if len(all_records) >= 2:
            start_id = f"{all_records[0].source_id}:{all_records[0].external_id}"
            target_id = f"{all_records[1].source_id}:{all_records[1].external_id}"
            discovered_paths = self.persister.find_path(start_id, target_id, max_hops=plan.traversal_depth)

        # 4. Synthesize findings
        findings: list[str] = []
        for rec in all_records:
            if rec.relationships:
                for rel in rec.relationships:
                    findings.append(
                        f"[{rel.confidence}] {rel.source_entity_id} -({rel.relation_type})-> {rel.target_entity_id} "
                        f"(Evidence: {rel.evidence_field})"
                    )

        if not findings and all_records:
            findings.append(
                f"Discovered {len(all_records)} discrete public entities; no direct graph edges connect them yet."
            )

        # Entity and Relationship summarization for UI
        entities_summary = [
            {
                "id": f"{r.source_id}:{r.external_id}",
                "type": r.entity_type,
                "name": r.data.get("title") or r.data.get("name") or r.external_id,
                "source": r.source_id,
                "url": r.canonical_url,
            }
            for r in all_records
        ]

        relationships_summary = []
        for r in all_records:
            for rel in r.relationships:
                relationships_summary.append(
                    {
                        "source": rel.source_entity_id,
                        "target": rel.target_entity_id,
                        "type": rel.relation_type,
                        "confidence": rel.confidence,
                        "evidence": rel.evidence_field,
                        "provenance_url": rel.provenance_url,
                    }
                )

        summary = (
            f"Universal Ask GAF analyzed {len(all_records)} entities and {len(relationships_summary)} "
            f"relationships across {len(plan.selected_source_ids)} public sources in "
            f"{(time.monotonic() - start_ts):.2f}s."
        )

        return UniversalInvestigationResult(
            question=question,
            plan=plan,
            sources_queried=sources_status,
            records_ingested=persist_counts.get("entities", 0),
            entities=entities_summary,
            relationships=relationships_summary,
            paths=discovered_paths,
            findings=findings,
            summary=summary,
            coverage_limitations=list(set(limitations)),
            execution_time_ms=(time.monotonic() - start_ts) * 1000.0,
        )
