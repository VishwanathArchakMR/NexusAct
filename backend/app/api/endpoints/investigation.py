"""Investigation and graph intelligence API endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.agent.planner import (
    AdaptiveInvestigationAgent,
    InvestigationReport,
)
from backend.app.graph.client import graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.centrality import (
    PageRankInput,
    PageRankOutput,
    execute_page_rank,
)
from backend.app.graph.tools.impact import (
    TraceImpactInput,
    TraceImpactOutput,
    execute_trace_impact,
)
from backend.app.graph.tools.reviewers import (
    WhoKnowsInput,
    WhoKnowsOutput,
    execute_who_knows,
)
from backend.app.graph.tools.simulation import (
    SimulateRemoveModuleInput,
    SimulationResult,
    execute_simulate_remove_module,
)
from backend.app.sources.registry import repo_registry

logger = logging.getLogger("nexusact.api.investigation")
router = APIRouter(tags=["Investigation & Graph Tools"])


class InvestigationRequest(BaseModel):
    question: str = Field(..., description="Investigation prompt or user engineering question")
    module_identifier: Optional[str] = Field(
        default=None,
        description="Optional target module ID or name (auto-resolved from natural language question if omitted)",
    )
    repo_id: Optional[str] = Field(default=None, description="Selected repository identifier")
    graph_name: Optional[str] = Field(default=None, description="Target graph name")
    max_budget: int = Field(default=5, ge=1, le=8, description="Maximum tool invocation budget")


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    evidence_type: str = "observed"
    properties: Dict[str, Any] = Field(default_factory=dict)


class SubgraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int


@router.post("/investigate", response_model=InvestigationReport)
async def run_investigation(payload: InvestigationRequest) -> InvestigationReport:
    """Runs the adaptive multi-step investigation loop across the graph."""
    try:
        agent = AdaptiveInvestigationAgent(max_tool_budget=payload.max_budget)
        report = await agent.investigate(
            question=payload.question,
            module_identifier=payload.module_identifier,
            repo_id=payload.repo_id,
            graph_name=payload.graph_name,
        )
        return report
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Investigation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.post("/tools/trace-impact", response_model=TraceImpactOutput)
def tool_trace_impact(payload: TraceImpactInput) -> TraceImpactOutput:
    """Executes bounded reverse dependency impact analysis (up to 4 hops)."""
    try:
        return execute_trace_impact(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("trace_impact failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/who-knows", response_model=WhoKnowsOutput)
def tool_who_knows(payload: WhoKnowsInput) -> WhoKnowsOutput:
    """Executes multi-hop reviewer discovery and expertise scoring."""
    try:
        return execute_who_knows(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("who_knows failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/page-rank", response_model=PageRankOutput)
def tool_page_rank(payload: PageRankInput) -> PageRankOutput:
    """Calculates structural centrality across the module graph using native PageRank."""
    try:
        return execute_page_rank(payload)
    except Exception as e:
        logger.error("page_rank failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/simulate", response_model=SimulationResult)
def tool_simulate_removal(payload: SimulateRemoveModuleInput) -> SimulationResult:
    """Runs isolated counterfactual module removal in a cloned graph."""
    try:
        return execute_simulate_remove_module(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("simulation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/subgraph", response_model=SubgraphResponse)
def get_graph_subgraph(
    center_module_id: Optional[str] = Query(default=None, description="Optional center module ID to bound subgraph"),
    depth: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=100, ge=1, le=300),
    repo_id: Optional[str] = Query(default=None, description="Repository identifier"),
    graph_name: Optional[str] = None,
) -> SubgraphResponse:
    # Normalize Query parameter objects if function is invoked directly in tests
    if not isinstance(center_module_id, str):
        center_module_id = None
    if not isinstance(depth, int):
        depth = 2
    if not isinstance(limit, int):
        limit = 100
    if not isinstance(repo_id, str):
        repo_id = None

    target_graph = graph_name
    if repo_id:
        repo_rec = repo_registry.get_repository(repo_id)
        if repo_rec:
            target_graph = repo_rec.graph_name
        elif not graph_name:
            return SubgraphResponse(nodes=[], edges=[], total_nodes=0, total_edges=0)
    if not target_graph:
        target_graph = graph_client.primary_graph_name

    try:
        if center_module_id:
            c_target = center_module_id if center_module_id.startswith("mod:") else f"mod:{center_module_id}"
            query_str = f"""
            MATCH (center:{LABEL_MODULE})
            WHERE center.id = $center_id OR center.id = $alt_id OR center.name = $center_id
            OPTIONAL MATCH p = (center)-[r:{REL_DEPENDS_ON}*1..{depth}]-(neighbor:{LABEL_MODULE})
            WITH center, collect(nodes(p)) AS path_nodes, collect(relationships(p)) AS path_rels
            RETURN center, path_nodes, path_rels
            LIMIT 1
            """
            raw = graph_client.query(
                query_str,
                params={"center_id": center_module_id, "alt_id": c_target},
                graph_name=target_graph,
            )
            nodes_map = {}
            edges_map = {}
            internal_to_business: Dict[Any, str] = {}

            if raw:
                center_node, path_nodes_list, path_rels_list = raw[0][0], raw[0][1], raw[0][2]
                center_props = getattr(center_node, "properties", {})
                c_id = center_props.get("id", str(getattr(center_node, "id", "center")))
                internal_to_business[getattr(center_node, "id", c_id)] = c_id
                nodes_map[c_id] = GraphNode(
                    id=c_id,
                    label=center_props.get("name", c_id),
                    type="Module",
                    properties=center_props,
                )

                for node_group in path_nodes_list or []:
                    for n in node_group or []:
                        props = getattr(n, "properties", {})
                        n_id = props.get("id", str(getattr(n, "id", "")))
                        if n_id:
                            internal_to_business[getattr(n, "id", n_id)] = n_id
                            if n_id not in nodes_map:
                                nodes_map[n_id] = GraphNode(
                                    id=n_id,
                                    label=props.get("name", n_id),
                                    type="Module",
                                    properties=props,
                                )

                for rel_group in path_rels_list or []:
                    for r in rel_group or []:
                        r_props = getattr(r, "properties", {})
                        raw_src = getattr(r, "src_node", None)
                        raw_dst = getattr(r, "dest_node", None)
                        src_id = internal_to_business.get(raw_src, str(raw_src))
                        dst_id = internal_to_business.get(raw_dst, str(raw_dst))
                        edge_id = r_props.get("id", f"{src_id}->{dst_id}")

                        # Ensure both ends exist in nodes_map to maintain strict graph integrity
                        if src_id in nodes_map and dst_id in nodes_map and edge_id not in edges_map:
                            edges_map[edge_id] = GraphEdge(
                                id=edge_id,
                                source=src_id,
                                target=dst_id,
                                label=getattr(r, "relation", REL_DEPENDS_ON),
                                evidence_type=r_props.get("evidence_type", "observed"),
                                properties=r_props,
                            )

            return SubgraphResponse(
                nodes=list(nodes_map.values()),
                edges=list(edges_map.values()),
                total_nodes=len(nodes_map),
                total_edges=len(edges_map),
            )
        else:
            # General overview module graph
            query_str = f"""
            MATCH (u:{LABEL_MODULE})-[r:{REL_DEPENDS_ON}]->(v:{LABEL_MODULE})
            RETURN u.id, u.name, v.id, v.name, r.id, r.evidence_type, r.source_file
            LIMIT $limit
            """
            rows = graph_client.query(query_str, params={"limit": limit}, graph_name=target_graph)

            nodes_map = {}
            edges_list = []

            for row in rows:
                u_id, u_name, v_id, v_name, r_id, ev_type, sf = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                if u_id not in nodes_map:
                    nodes_map[u_id] = GraphNode(id=u_id, label=u_name or u_id, type="Module")
                if v_id not in nodes_map:
                    nodes_map[v_id] = GraphNode(id=v_id, label=v_name or v_id, type="Module")

                edges_list.append(
                    GraphEdge(
                        id=r_id or f"{u_id}->{v_id}",
                        source=u_id,
                        target=v_id,
                        label=REL_DEPENDS_ON,
                        evidence_type=ev_type or "observed",
                        properties={"source_file": sf} if sf else {},
                    )
                )

            return SubgraphResponse(
                nodes=list(nodes_map.values()),
                edges=edges_list,
                total_nodes=len(nodes_map),
                total_edges=len(edges_list),
            )
    except Exception as e:
        logger.error("Failed to query subgraph: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
