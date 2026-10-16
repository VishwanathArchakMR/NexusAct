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
    """Structured, bounded plan for public-data or repository graph investigation."""

    plan_id: str = Field(default_factory=lambda: f"uplan_{uuid.uuid4().hex[:8]}")
    question: str
    input_mode: str = "public"
    repository_id: str | None = None
    graph_name: str | None = None
    commit_sha: str | None = None
    target_entity_types: list[str] = Field(default_factory=list)
    relationship_focus: list[str] = Field(default_factory=list)
    selected_source_ids: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    max_results_per_source: int = 5
    traversal_depth: int = 2
    is_heuristic_fallback: bool = True


class UniversalInvestigationResult(BaseModel):
    """Complete, evidence-backed result of an input-driven GAF investigation."""

    investigation_id: str = Field(default_factory=lambda: f"uinv_{uuid.uuid4().hex[:8]}")
    input_mode: str = "public"
    repository_id: str | None = None
    graph_name: str | None = None
    commit_sha: str | None = None
    question: str
    plan: UniversalInvestigationPlan
    sources_queried: dict[str, dict[str, Any]] = Field(default_factory=dict)
    records_ingested: int = 0
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    summary: str = ""
    approach: str = ""
    next_action: dict[str, Any] | None = None
    coverage_limitations: list[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    context: dict[str, Any] = Field(default_factory=dict)
    scoped_subgraph: dict[str, Any] = Field(
        default_factory=lambda: {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}
    )


class UniversalDiscoveryPlanner:
    """Plans and executes bounded investigations across public data sources."""

    def __init__(self, persister: PublicGraphPersister | None = None) -> None:
        self.persister = persister or PublicGraphPersister()

    def create_plan(
        self,
        question: str,
        input_mode: str = "public",
        repository_id: str | None = None,
        graph_name: str | None = None,
        commit_sha: str | None = None,
    ) -> UniversalInvestigationPlan:
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

        # Extract search keywords: remove purely grammatical stop words
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
            "tell",
            "me",
            "about",
            "between",
            "this",
            "these",
            "for",
            "of",
            "does",
            "can",
            "with",
            "from",
            "across",
            "documented",
            "as",
        }
        words = re.findall(r"[A-Za-z0-9_-]+", q_lower)
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Search term selection
        search_term = " ".join(keywords[:3]) if keywords else "artificial intelligence"

        return UniversalInvestigationPlan(
            question=question,
            target_entity_types=target_entities,
            relationship_focus=rel_focus or ["USES_DATASET", "AUTHORED", "CITES", "AFFILIATED_WITH"],
            selected_source_ids=list(selected_sources),
            search_keywords=[search_term],
            max_results_per_source=5,
            traversal_depth=2,
            is_heuristic_fallback=True,
            input_mode=input_mode,
            repository_id=repository_id,
            graph_name=graph_name,
            commit_sha=commit_sha,
        )

    def execute_investigation(
        self,
        question: str,
        plan_override: UniversalInvestigationPlan | None = None,
        input_mode: str = "public",
        repository_id: str | None = None,
        graph_name: str | None = None,
        commit_sha: str | None = None,
    ) -> UniversalInvestigationResult:
        """Executes the investigation plan across public data sources or repository graphs."""
        start_ts = time.monotonic()
        plan = plan_override or self.create_plan(question)

        effective_mode = (
            plan_override.input_mode if plan_override and plan_override.input_mode != "public" else input_mode
        )
        effective_repo_id = repository_id or (plan_override.repository_id if plan_override else None)
        effective_graph = graph_name or (plan_override.graph_name if plan_override else None)
        effective_sha = commit_sha or (plan_override.commit_sha if plan_override else None)

        if effective_mode == "repository":
            return self._execute_repository_investigation(
                question=question,
                plan=plan,
                repo_id=effective_repo_id or "repo:local_nexusact",
                target_graph=effective_graph,
                commit_sha=effective_sha,
                start_ts=start_ts,
            )
        elif effective_mode == "combined":
            return self._execute_combined_investigation(
                question=question,
                plan=plan,
                repo_id=effective_repo_id or "repo:local_nexusact",
                target_graph=effective_graph,
                commit_sha=effective_sha,
                start_ts=start_ts,
            )
        else:
            return self._execute_public_investigation(
                question=question,
                plan=plan,
                start_ts=start_ts,
            )

    def _execute_repository_investigation(
        self,
        question: str,
        plan: UniversalInvestigationPlan,
        repo_id: str,
        target_graph: str | None,
        commit_sha: str | None,
        start_ts: float,
    ) -> UniversalInvestigationResult:
        """Analyzes a selected code repository graph, extracting actual modules and dependency edges."""
        from backend.app.sources.registry import repo_registry

        repo = repo_registry.get_repository(repo_id)
        repo_name = repo.name if repo else repo_id
        effective_graph = target_graph or (repo.graph_name if repo else "nexusact_main")
        effective_sha = commit_sha or (repo.commit_sha if repo else "HEAD")

        limitations: list[str] = []
        if repo and repo.known_gaps:
            limitations.extend(repo.known_gaps)

        # Query modules and dependencies from repository graph
        try:
            mod_query = """
            MATCH (m:Module)
            OPTIONAL MATCH (m)-[r:DEPENDS_ON]->(dep:Module)
            RETURN m.id AS mod_id, coalesce(m.name, m.id) AS mod_name, properties(m) AS mod_props,
                   dep.id AS dep_id, coalesce(dep.name, dep.id) AS dep_name,
                   r.evidence_type AS ev_type, r.source_file AS src_file
            LIMIT 100
            """
            rows = self.persister.client.query(mod_query, graph_name=effective_graph)
        except Exception as exc:
            logger.warning("Failed querying repository graph '%s': %s", effective_graph, exc)
            rows = []
            limitations.append(f"Failed querying repository graph '{effective_graph}': {exc}")

        entities_map: dict[str, dict[str, Any]] = {}
        relationships: list[dict[str, Any]] = []
        scoped_nodes: list[dict[str, Any]] = []
        scoped_edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str, str]] = set()

        for row in rows:
            mod_id = str(row[0])
            mod_name = str(row[1])
            mod_props = row[2] if len(row) > 2 and isinstance(row[2], dict) else {}
            dep_id = str(row[3]) if row[3] else None
            dep_name = str(row[4]) if row[4] else None
            ev_type = str(row[5]) if len(row) > 5 and row[5] else "observed"
            src_file = str(row[6]) if len(row) > 6 and row[6] else None

            if mod_id and mod_id not in entities_map:
                ent = {
                    "id": mod_id,
                    "type": "Module",
                    "name": mod_name,
                    "source": f"repo:{repo_name}",
                    "domain": "software",
                    "properties": mod_props,
                }
                entities_map[mod_id] = ent
                scoped_nodes.append(
                    {
                        "id": mod_id,
                        "label": mod_name,
                        "type": "Module",
                        "domain": "software",
                        "properties": mod_props,
                    }
                )

            if dep_id:
                if dep_id not in entities_map:
                    ent = {
                        "id": dep_id,
                        "type": "Module",
                        "name": dep_name or dep_id,
                        "source": f"repo:{repo_name}",
                        "domain": "software",
                        "properties": {},
                    }
                    entities_map[dep_id] = ent
                    scoped_nodes.append(
                        {
                            "id": dep_id,
                            "label": dep_name or dep_id,
                            "type": "Module",
                            "domain": "software",
                            "properties": {},
                        }
                    )

                edge_key = (mod_id, "DEPENDS_ON", dep_id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    rel = {
                        "source": mod_id,
                        "target": dep_id,
                        "type": "DEPENDS_ON",
                        "domain": "software",
                        "confidence": "EXACT",
                        "evidence": f"AST import in {src_file or 'source'}",
                        "provenance_url": f"repo:{repo_id}/{src_file or ''}",
                    }
                    relationships.append(rel)
                    scoped_edges.append(
                        {
                            "source": mod_id,
                            "target": dep_id,
                            "type": "DEPENDS_ON",
                            "label": "DEPENDS_ON",
                            "domain": "software",
                            "confidence": "EXACT",
                            "evidence": f"AST import in {src_file or 'source'}",
                            "provenance_url": f"repo:{repo_id}/{src_file or ''}",
                            "properties": {"evidence_type": ev_type, "source_file": src_file},
                        }
                    )

        entities_list = list(entities_map.values())

        if not entities_list:
            limitations.append(
                f"Selected repository '{repo_id}' currently has 0 parsed modules and "
                f"0 dependency edges in graph '{effective_graph}'. "
                f"Run ingestion on this repository to extract code structure."
            )
            summary = (
                f"Repository investigation on '{repo_name}' [{effective_graph} @ {effective_sha[:7]}]: "
                f"0 modules found in graph. Repository requires code structure ingestion."
            )
            findings = [
                f"Repository '{repo_name}' is registered but graph '{effective_graph}' has 0 extracted modules.",
                "No dependency relationships or reviewer experience can be traced until ingestion is executed.",
            ]
            next_action = {
                "id": f"act_ingest_{uuid.uuid4().hex[:8]}",
                "title": f"Ingest repository {repo_name}",
                "description": f"Trigger AST parsing and dependency extraction for repository '{repo_id}'.",
                "status": "PROPOSED",
            }
        else:
            summary = (
                f"Investigated repository '{repo_name}' on graph '{effective_graph}' (commit {effective_sha[:7]}): "
                f"Analyzed {len(entities_list)} modules and {len(relationships)} dependency relationships."
            )
            findings = [
                f"Repository '{repo_name}' (graph: {effective_graph}, rev: {effective_sha[:7]}) contains "
                f"{len(entities_list)} parsed modules and {len(relationships)} direct dependency edges.",
            ]
            for r in relationships[:5]:
                findings.append(f"[EXACT] {r['source']} -(DEPENDS_ON)-> {r['target']} ({r['evidence']})")
            if len(relationships) > 5:
                findings.append(
                    f"... and {len(relationships) - 5} additional dependency relationships verified in graph."
                )

            top_mod = entities_list[0]["name"] if entities_list else "core"
            next_action = {
                "id": f"act_trace_{uuid.uuid4().hex[:8]}",
                "title": f"Run counterfactual simulation on {top_mod}",
                "description": f"Simulate blast radius and isolated modules if '{top_mod}' is modified or refactored.",
                "status": "PROPOSED",
            }

        approach = (
            f"Input Mode: Selected Repository ({repo_name}). Routed question to graph '{effective_graph}' "
            f"at revision {effective_sha[:7]}. Executed Cypher traversal for module definitions and DEPENDS_ON edges."
        )

        return UniversalInvestigationResult(
            input_mode="repository",
            repository_id=repo_id,
            graph_name=effective_graph,
            commit_sha=effective_sha,
            question=question,
            plan=plan,
            sources_queried={
                repo_id: {
                    "source_id": repo_id,
                    "records_fetched": len(entities_list),
                    "graph_name": effective_graph,
                    "commit_sha": effective_sha,
                }
            },
            records_ingested=len(entities_list),
            entities=entities_list,
            relationships=relationships,
            paths=[],
            findings=findings,
            summary=summary,
            approach=approach,
            next_action=next_action,
            coverage_limitations=list(set(limitations)),
            execution_time_ms=(time.monotonic() - start_ts) * 1000.0,
            context={
                "input_mode": "repository",
                "repository_id": repo_id,
                "repository_name": repo_name,
                "graph_name": effective_graph,
                "commit_sha": effective_sha,
            },
            scoped_subgraph={
                "nodes": scoped_nodes,
                "edges": scoped_edges,
                "total_nodes": len(scoped_nodes),
                "total_edges": len(scoped_edges),
            },
        )

    def _execute_combined_investigation(
        self,
        question: str,
        plan: UniversalInvestigationPlan,
        repo_id: str,
        target_graph: str | None,
        commit_sha: str | None,
        start_ts: float,
    ) -> UniversalInvestigationResult:
        """Executes both repository graph analysis and public knowledge retrieval with distinct domain provenance."""
        repo_res = self._execute_repository_investigation(
            question=question,
            plan=plan,
            repo_id=repo_id,
            target_graph=target_graph,
            commit_sha=commit_sha,
            start_ts=start_ts,
        )

        public_res = self._execute_public_investigation(
            question=question,
            plan=plan,
            start_ts=start_ts,
        )

        merged_entities = list(repo_res.entities) + list(public_res.entities)
        merged_relationships = list(repo_res.relationships) + list(public_res.relationships)

        limitations = list(repo_res.coverage_limitations) + list(public_res.coverage_limitations)
        limitations.append(
            f"No explicit cross-domain references (DOI, arXiv ID, or Hugging Face model identifier) "
            f"link repository '{repo_id}' with the retrieved public records. Subgraphs are presented separately."
        )

        combined_nodes = list(repo_res.scoped_subgraph.get("nodes", [])) + list(
            public_res.scoped_subgraph.get("nodes", [])
        )
        combined_edges = list(repo_res.scoped_subgraph.get("edges", [])) + list(
            public_res.scoped_subgraph.get("edges", [])
        )

        merged_findings = (
            [f"--- Repository Domain ({repo_res.repository_id}) ---"]
            + repo_res.findings
            + ["--- Public Research & Model Domain ---"]
            + public_res.findings
        )

        summary = (
            f"Combined Investigation: Analyzed {len(repo_res.entities)} codebase modules in "
            f"'{repo_res.repository_id}' and {len(public_res.entities)} public entities across "
            f"{len(plan.selected_source_ids)} public sources."
        )

        sources_str = ", ".join(plan.selected_source_ids)
        approach = (
            f"Combined Scope: (1) Repo '{repo_res.repository_id}' on graph '{repo_res.graph_name}'. "
            f"(2) Public discovery across [{sources_str}]. Presented with separate domain provenance."
        )

        return UniversalInvestigationResult(
            input_mode="combined",
            repository_id=repo_res.repository_id,
            graph_name=repo_res.graph_name,
            commit_sha=repo_res.commit_sha,
            question=question,
            plan=plan,
            sources_queried={**repo_res.sources_queried, **public_res.sources_queried},
            records_ingested=repo_res.records_ingested + public_res.records_ingested,
            entities=merged_entities,
            relationships=merged_relationships,
            paths=public_res.paths,
            findings=merged_findings,
            summary=summary,
            approach=approach,
            next_action=repo_res.next_action or public_res.next_action,
            coverage_limitations=list(set(limitations)),
            execution_time_ms=(time.monotonic() - start_ts) * 1000.0,
            context={
                "input_mode": "combined",
                "repository_id": repo_res.repository_id,
                "graph_name": repo_res.graph_name,
                "commit_sha": repo_res.commit_sha,
                "selected_sources": plan.selected_source_ids,
            },
            scoped_subgraph={
                "nodes": combined_nodes,
                "edges": combined_edges,
                "total_nodes": len(combined_nodes),
                "total_edges": len(combined_edges),
            },
        )

    def _execute_public_investigation(
        self,
        question: str,
        plan: UniversalInvestigationPlan,
        start_ts: float,
    ) -> UniversalInvestigationResult:
        """Executes the public data investigation plan: queries sources, deduplicates, persists, and analyzes paths."""
        dedup_records: dict[str, SourceRecord] = {}
        sources_status: dict[str, dict[str, Any]] = {}
        limitations: list[str] = []

        # 1. Fetch bounded records from selected connectors with canonical deduplication
        raw_to_canon: dict[str, str] = {}
        for source_id in plan.selected_source_ids:
            connector = ConnectorRegistry.get(source_id)
            if not connector:
                limitations.append(f"Connector '{source_id}' is not registered or unavailable.")
                continue

            connector_query_text = plan.search_keywords[0] if plan.search_keywords else "machine learning"
            query = ConnectorQuery(
                query_text=connector_query_text,
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
                for rec in res.records:
                    doi = rec.data.get("doi")
                    if doi and rec.entity_type == "Paper":
                        norm_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                        canon_key = f"doi:{norm_doi}"
                    else:
                        canon_key = f"{rec.source_id}:{rec.external_id}"

                    raw_id = f"{rec.source_id}:{rec.external_id}"
                    raw_to_canon[raw_id] = canon_key

                    for rel in rec.relationships:
                        if rel.source_entity_id == raw_id:
                            rel.source_entity_id = canon_key

                    if canon_key in dedup_records:
                        existing = dedup_records[canon_key]
                        existing_rel_keys = {
                            (r.source_entity_id, r.relation_type, r.target_entity_id) for r in existing.relationships
                        }
                        for rel in rec.relationships:
                            rel_key = (rel.source_entity_id, rel.relation_type, rel.target_entity_id)
                            if rel_key not in existing_rel_keys:
                                existing.relationships.append(rel)
                                existing_rel_keys.add(rel_key)
                        existing.coverage_notes = list(set(existing.coverage_notes + rec.coverage_notes))
                    else:
                        dedup_records[canon_key] = rec

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

        all_records = list(dedup_records.values())

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

        canonical_map: dict[str, str] = dict(raw_to_canon)
        for r in all_records:
            ent_raw_id = f"{r.source_id}:{r.external_id}"
            doi = r.data.get("doi")
            if doi and r.entity_type == "Paper":
                norm_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                canon_id = f"doi:{norm_doi}"
            else:
                canon_id = ent_raw_id
            canonical_map[ent_raw_id] = canon_id

        seen_ent_ids: set[str] = set()
        entities_summary = []
        scoped_nodes = []
        for r in all_records:
            ent_raw_id = f"{r.source_id}:{r.external_id}"
            ent_id = canonical_map.get(ent_raw_id, ent_raw_id)
            if ent_id not in seen_ent_ids:
                seen_ent_ids.add(ent_id)
                ent_name = r.data.get("title") or r.data.get("name") or r.external_id
                entities_summary.append(
                    {
                        "id": ent_id,
                        "type": r.entity_type,
                        "name": ent_name,
                        "source": r.source_id,
                        "domain": "public",
                        "url": r.canonical_url,
                    }
                )
                scoped_nodes.append(
                    {
                        "id": ent_id,
                        "label": ent_name,
                        "type": r.entity_type,
                        "domain": "public",
                        "properties": {"source": r.source_id, "url": r.canonical_url, "external_id": r.external_id},
                    }
                )

        seen_rel_keys: set[tuple[str, str, str]] = set()
        relationships_summary = []
        scoped_edges = []
        for r in all_records:
            for rel in r.relationships:
                canon_src = canonical_map.get(rel.source_entity_id, rel.source_entity_id)
                canon_tgt = canonical_map.get(rel.target_entity_id, rel.target_entity_id)
                rel_key = (canon_src, rel.relation_type, canon_tgt)
                if rel_key not in seen_rel_keys:
                    seen_rel_keys.add(rel_key)
                    rel_dict = {
                        "source": canon_src,
                        "target": canon_tgt,
                        "type": rel.relation_type,
                        "domain": "public",
                        "confidence": rel.confidence,
                        "evidence": rel.evidence_field,
                        "provenance_url": rel.provenance_url,
                    }
                    relationships_summary.append(rel_dict)
                    scoped_edges.append(
                        {
                            "source": canon_src,
                            "target": canon_tgt,
                            "type": rel.relation_type,
                            "label": rel.relation_type,
                            "domain": "public",
                            "confidence": rel.confidence,
                            "evidence": rel.evidence_field,
                            "provenance_url": rel.provenance_url,
                            "properties": {},
                        }
                    )

        summary = (
            f"Universal Ask GAF analyzed {len(all_records)} entities and {len(relationships_summary)} "
            f"relationships across {len(plan.selected_source_ids)} public sources in "
            f"{(time.monotonic() - start_ts):.2f}s."
        )

        sources_list = ", ".join(plan.selected_source_ids)
        approach_desc = (
            f"Selected connectors: [{sources_list}] targeting entity types {plan.target_entity_types}. "
            f"Executed bounded semantic retrieval with canonical DOI reconciliation, FalkorDB graph persistence, "
            f"and multi-hop traversal bounded to {plan.traversal_depth} hops."
        )

        top_entity_name = entities_summary[0]["name"] if entities_summary else "investigated topic"
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        next_action_dict = {
            "id": action_id,
            "title": f"Track upstream citations & updates for {top_entity_name}",
            "description": (
                f"Register a follow-up graph monitor task to track incoming citations "
                f"and derivative works for '{top_entity_name}'."
            ),
            "status": "PROPOSED",
        }

        return UniversalInvestigationResult(
            input_mode="public",
            question=question,
            plan=plan,
            sources_queried=sources_status,
            records_ingested=persist_counts.get("entities", 0),
            entities=entities_summary,
            relationships=relationships_summary,
            paths=discovered_paths,
            findings=findings,
            summary=summary,
            approach=approach_desc,
            next_action=next_action_dict,
            coverage_limitations=list(set(limitations)),
            execution_time_ms=(time.monotonic() - start_ts) * 1000.0,
            context={
                "input_mode": "public",
                "selected_sources": plan.selected_source_ids,
            },
            scoped_subgraph={
                "nodes": scoped_nodes,
                "edges": scoped_edges,
                "total_nodes": len(scoped_nodes),
                "total_edges": len(scoped_edges),
            },
        )
