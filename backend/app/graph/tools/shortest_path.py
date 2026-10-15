"""Shortest path analysis tool between two modules in the dependency graph."""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.impact import resolve_module_id

logger = logging.getLogger("nexusact.tools.shortest_path")


class ShortestPathOutput(BaseModel):
    source_id: str
    target_id: str
    connected: bool
    hops: int = 0
    path_nodes: List[str] = Field(default_factory=list)
    explanation: str = ""


class ShortestPathInput(BaseModel):
    source_identifier: str = Field(..., description="Source module name or ID")
    target_identifier: str = Field(..., description="Target module name or ID")
    graph_name: Optional[str] = Field(default=None)


def execute_shortest_path(
    payload: ShortestPathInput,
    client: Optional[FalkorDBClient] = None,
) -> ShortestPathOutput:
    """Finds the shortest directed dependency path from source to target."""
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name

    src_id = resolve_module_id(cli, payload.source_identifier, graph_name=target_graph)
    if not src_id:
        raise ValueError(f"Source module '{payload.source_identifier}' could not be resolved.")

    tgt_id = resolve_module_id(cli, payload.target_identifier, graph_name=target_graph)
    if not tgt_id:
        raise ValueError(f"Target module '{payload.target_identifier}' could not be resolved.")

    if src_id == tgt_id:
        return ShortestPathOutput(
            source_id=src_id,
            target_id=tgt_id,
            connected=True,
            hops=0,
            path_nodes=[src_id],
            explanation=f"Source and target are identical ({src_id}).",
        )

    # Use bounded length shortest path in Cypher
    rows = cli.query(
        f"""
        MATCH p = (src:{LABEL_MODULE} {{id: $src_id}})-[:{REL_DEPENDS_ON}*1..6]->(tgt:{LABEL_MODULE} {{id: $tgt_id}})
        RETURN [n IN nodes(p) | n.id], length(p)
        ORDER BY length(p) ASC
        LIMIT 1
        """,
        params={"src_id": src_id, "tgt_id": tgt_id},
        graph_name=target_graph,
    )

    if rows:
        path = [str(x) for x in rows[0][0]] if isinstance(rows[0][0], list) else []
        hops = rows[0][1]
        path_str = " -> ".join([str(p) for p in path])
        return ShortestPathOutput(
            source_id=src_id,
            target_id=tgt_id,
            connected=True,
            hops=hops,
            path_nodes=path,
            explanation=f"Connected in {hops} hop(s): {path_str}.",
        )
    else:
        return ShortestPathOutput(
            source_id=src_id,
            target_id=tgt_id,
            connected=False,
            hops=-1,
            path_nodes=[],
            explanation=f"No directed dependency path found from '{src_id}' to '{tgt_id}' within 6 hops.",
        )
