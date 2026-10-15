"""Graph structural centrality calculation tool using FalkorDB native PageRank."""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON

logger = logging.getLogger("nexusact.tools.centrality")


class PageRankEntry(BaseModel):
    module_id: str
    module_name: str
    score: float = Field(..., description="Calculated PageRank centrality score")
    rank: int


class PageRankInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of top modules to return")
    graph_name: Optional[str] = Field(default=None, description="Target graph name")


class PageRankOutput(BaseModel):
    graph_name: str
    target_label: str = LABEL_MODULE
    target_relationship: str = REL_DEPENDS_ON
    top_modules: List[PageRankEntry] = Field(default_factory=list)
    interpretation: str = (
        "PageRank identifies structurally central modules that many components directly or indirectly depend upon. "
        "High score indicates high architectural impact if modified, but does not measure runtime failure likelihood."
    )


def execute_page_rank(
    payload: PageRankInput,
    client: Optional[FalkorDBClient] = None,
) -> PageRankOutput:
    """Executes FalkorDB native PageRank algorithm across the dependency graph."""
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name

    query_str = f"CALL algo.pageRank('{LABEL_MODULE}', '{REL_DEPENDS_ON}')"
    raw_results = cli.query(query_str, graph_name=target_graph)

    entries: List[PageRankEntry] = []
    for row in raw_results:
        node, score = row[0], float(row[1])
        props = getattr(node, "properties", {}) if hasattr(node, "properties") else {}
        mod_id = props.get("id", str(getattr(node, "id", "unknown")))
        mod_name = props.get("name", mod_id)

        entries.append(
            PageRankEntry(
                module_id=mod_id,
                module_name=mod_name,
                score=round(score, 5),
                rank=0,
            )
        )

    # Sort descending by PageRank score
    entries.sort(key=lambda e: e.score, reverse=True)
    top_entries = entries[: payload.limit]
    for idx, e in enumerate(top_entries):
        e.rank = idx + 1

    return PageRankOutput(
        graph_name=target_graph,
        top_modules=top_entries,
    )
