"""Bounded graph neighborhood inspection tool."""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.impact import resolve_module_id

logger = logging.getLogger("nexusact.tools.neighborhood")


class NeighborhoodNode(BaseModel):
    id: str
    name: str
    direction: str  # "incoming_dependent" or "outgoing_dependency"
    source_file: Optional[str] = None


class GraphNeighborhoodOutput(BaseModel):
    target_module_id: str
    target_module_name: str
    incoming_dependents: List[NeighborhoodNode]
    outgoing_dependencies: List[NeighborhoodNode]
    total_neighbors: int


class GraphNeighborhoodInput(BaseModel):
    module_identifier: str = Field(..., description="Target module name or ID")
    limit: int = Field(default=30, ge=1, le=100)
    graph_name: Optional[str] = Field(default=None)


def execute_graph_neighborhood(
    payload: GraphNeighborhoodInput,
    client: Optional[FalkorDBClient] = None,
) -> GraphNeighborhoodOutput:
    """Inspects immediate 1-hop incoming and outgoing dependency connections."""
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name

    resolved_id = resolve_module_id(cli, payload.module_identifier, graph_name=target_graph)
    if not resolved_id:
        raise ValueError(f"Module '{payload.module_identifier}' could not be resolved.")

    name_res = cli.query(
        f"MATCH (m:{LABEL_MODULE} {{id: $id}}) RETURN m.name LIMIT 1",
        params={"id": resolved_id},
        graph_name=target_graph,
    )
    mod_name = name_res[0][0] if name_res else resolved_id

    # 1. Incoming dependents: (u)-[r:DEPENDS_ON]->(target)
    inc_rows = cli.query(
        f"""
        MATCH (u:{LABEL_MODULE})-[r:{REL_DEPENDS_ON}]->(t:{LABEL_MODULE} {{id: $tid}})
        RETURN u.id, u.name, r.source_file
        LIMIT $limit
        """,
        params={"tid": resolved_id, "limit": payload.limit},
        graph_name=target_graph,
    )
    incoming = [
        NeighborhoodNode(
            id=r[0],
            name=r[1] or r[0],
            direction="incoming_dependent",
            source_file=r[2],
        )
        for r in inc_rows
    ]

    # 2. Outgoing dependencies: (target)-[r:DEPENDS_ON]->(v)
    out_rows = cli.query(
        f"""
        MATCH (t:{LABEL_MODULE} {{id: $tid}})-[r:{REL_DEPENDS_ON}]->(v:{LABEL_MODULE})
        RETURN v.id, v.name, r.source_file
        LIMIT $limit
        """,
        params={"tid": resolved_id, "limit": payload.limit},
        graph_name=target_graph,
    )
    outgoing = [
        NeighborhoodNode(
            id=r[0],
            name=r[1] or r[0],
            direction="outgoing_dependency",
            source_file=r[2],
        )
        for r in out_rows
    ]

    return GraphNeighborhoodOutput(
        target_module_id=resolved_id,
        target_module_name=mod_name,
        incoming_dependents=incoming,
        outgoing_dependencies=outgoing,
        total_neighbors=len(incoming) + len(outgoing),
    )
