"""Reverse-dependency impact analysis tool (trace_impact)."""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON, format_module_id

logger = logging.getLogger("nexusact.tools.impact")


class DependencyPathNode(BaseModel):
    id: str
    name: str


class ImpactedModule(BaseModel):
    module_id: str
    module_name: str
    hops: int
    path: List[str] = Field(description="Ordered module IDs from dependent upstream to target")
    source_files: List[str] = Field(default_factory=list, description="Source files defining dependencies along path")


class TraceImpactInput(BaseModel):
    module_identifier: str = Field(..., description="Module ID (e.g. mod:pkg) or module name")
    max_depth: int = Field(default=4, ge=1, le=4, description="Bounded reverse traversal depth (1 to 4 hops)")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of impacted paths to return")
    graph_name: Optional[str] = Field(default=None, description="Optional target graph name")


class TraceImpactOutput(BaseModel):
    target_module_id: str
    target_module_name: str
    max_depth: int
    impacted_modules: List[ImpactedModule] = Field(default_factory=list)
    total_impacted_count: int = 0
    is_truncated: bool = False
    evidence_type: str = "observed"
    traversal_direction: str = "upstream_dependent_to_target"
    caveat: str = "Static graph dependency does not guarantee runtime failure."


def resolve_module_id(client: FalkorDBClient, identifier: str, graph_name: Optional[str] = None) -> Optional[str]:
    """Resolves an input string (name or id) to an existing stable module ID in the graph."""
    cleaned = identifier.strip()
    target_graph = graph_name or client.primary_graph_name

    # Try direct ID
    candidates = [cleaned, format_module_id(cleaned)]
    if cleaned.startswith("mod:"):
        candidates.append(cleaned[4:])

    for cand in candidates:
        res = client.query(
            "MATCH (m:Module) WHERE m.id = $cand OR m.name = $cand RETURN m.id LIMIT 1",
            params={"cand": cand},
            graph_name=target_graph,
        )
        if res and len(res) > 0:
            return res[0][0]

    return None


def execute_trace_impact(
    payload: TraceImpactInput,
    client: Optional[FalkorDBClient] = None,
) -> TraceImpactOutput:
    """Executes a bounded 4-hop reverse-dependency impact analysis."""
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name

    resolved_id = resolve_module_id(cli, payload.module_identifier, graph_name=target_graph)
    if not resolved_id:
        raise ValueError(f"Module '{payload.module_identifier}' could not be resolved in graph '{target_graph}'.")

    # Fetch module name
    name_res = cli.query(
        "MATCH (m:Module {id: $id}) RETURN m.name LIMIT 1",
        params={"id": resolved_id},
        graph_name=target_graph,
    )
    mod_name = name_res[0][0] if name_res else resolved_id

    # Canonical direction: DependentModule -[:DEPENDS_ON]-> DependencyModule
    # Upstream dependent modules point towards the target dependency:
    # (upstream)-[:DEPENDS_ON*1..max_depth]->(target)
    depth = min(max(payload.max_depth, 1), 4)
    query_str = f"""
    MATCH p = (upstream:{LABEL_MODULE})-[r:{REL_DEPENDS_ON}*1..{depth}]->(target:{LABEL_MODULE} {{id: $target_id}})
    WHERE upstream.id <> target.id
    RETURN upstream.id AS upstream_id,
           upstream.name AS upstream_name,
           length(p) AS hops,
           [n IN nodes(p) | n.id] AS path_ids,
           [rel IN relationships(p) | rel.source_file] AS source_files
    ORDER BY hops ASC
    LIMIT $fetch_limit
    """
    fetch_limit = payload.limit + 1
    raw_results = cli.query(
        query_str,
        params={"target_id": resolved_id, "fetch_limit": fetch_limit},
        graph_name=target_graph,
    )

    is_truncated = len(raw_results) > payload.limit
    results_slice = raw_results[: payload.limit]

    impacted: List[ImpactedModule] = []
    seen_ids = set()

    for row in results_slice:
        up_id, up_name, hops, path_ids, source_files = row[0], row[1], row[2], row[3], row[4]
        # Keep shortest hop per module
        if up_id not in seen_ids:
            seen_ids.add(up_id)
            impacted.append(
                ImpactedModule(
                    module_id=up_id,
                    module_name=up_name or up_id,
                    hops=hops,
                    path=[str(p) for p in path_ids] if isinstance(path_ids, list) else [],
                    source_files=[str(sf) for sf in source_files if sf] if isinstance(source_files, list) else [],
                )
            )

    return TraceImpactOutput(
        target_module_id=resolved_id,
        target_module_name=mod_name,
        max_depth=depth,
        impacted_modules=impacted,
        total_impacted_count=len(impacted),
        is_truncated=is_truncated,
    )
