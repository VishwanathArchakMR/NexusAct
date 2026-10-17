"""Investigation and graph intelligence API endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.agent.chat import (
    ChatInvestigationRequest,
    ChatInvestigationResponse,
    GraphChatService,
)
from backend.app.agent.explanation import (
    PanelExplanationRequest,
    PanelExplanationResponse,
    generate_panel_explanation,
)
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
from backend.app.graph.tools.fraud import (
    FraudInvestigationInput,
    FraudInvestigationOutput,
    execute_investigate_fraud,
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
from backend.app.graph.tools.security_triage import (
    SecurityTriageInput,
    SecurityTriageOutput,
    execute_security_triage,
)
from backend.app.graph.tools.simulation import (
    SimulateRemoveModuleInput,
    SimulationResult,
    execute_simulate_remove_module,
)
from backend.app.sources.registry import repo_registry

logger = logging.getLogger("nexusact.api.investigation")
router = APIRouter(prefix="/investigation", tags=["Investigation & Graph Intelligence"])
tools_router = APIRouter(prefix="/tools", tags=["Graph Tools"])
graph_router = APIRouter(prefix="/graph", tags=["Graph Subgraph"])


class InvestigationRequest(BaseModel):
    question: str = Field(..., description="Investigation prompt or user engineering question")
    module_identifier: Optional[str] = Field(
        default=None,
        description="Optional target module ID or name (auto-resolved from natural language question if omitted)",
    )
    repo_id: Optional[str] = Field(default=None, description="Selected repository identifier")
    graph_name: Optional[str] = Field(default=None, description="Target graph name")
    max_budget: int = Field(default=5, ge=1, le=8, description="Maximum tool invocation budget")
    investigation_mode: Optional[str] = Field(
        default=None,
        description="Optional mode: codebase_walkthrough, change_impact, security_triage, fraud_demo",
    )


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


@router.post(
    "/run",
    response_model=InvestigationReport,
    summary="Runs adaptive multi-step investigation loop across graph",
)
@router.post(
    "/investigate",
    response_model=InvestigationReport,
    summary="Runs adaptive multi-step investigation loop across graph",
)
async def run_investigation(payload: InvestigationRequest) -> InvestigationReport:
    """Runs the adaptive multi-step investigation loop across the graph."""
    try:
        agent = AdaptiveInvestigationAgent(max_tool_budget=payload.max_budget)
        report = await agent.investigate(
            question=payload.question,
            module_identifier=payload.module_identifier,
            repo_id=payload.repo_id,
            graph_name=payload.graph_name,
            investigation_mode=payload.investigation_mode,
        )
        return report
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Investigation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.post("/explain-panel", response_model=PanelExplanationResponse)
async def explain_investigation_panel(payload: PanelExplanationRequest) -> PanelExplanationResponse:
    """Generates an evidence-grounded structured explanation for a specific investigation panel."""
    try:
        return await generate_panel_explanation(payload)
    except Exception as e:
        logger.error("Panel explanation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")


@tools_router.post("/trace-impact", response_model=TraceImpactOutput)
def tool_trace_impact(payload: TraceImpactInput) -> TraceImpactOutput:
    """Executes bounded reverse dependency impact analysis (up to 4 hops)."""
    try:
        return execute_trace_impact(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("trace_impact failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@tools_router.post("/who-knows", response_model=WhoKnowsOutput)
def tool_who_knows(payload: WhoKnowsInput) -> WhoKnowsOutput:
    """Executes multi-hop reviewer discovery and expertise scoring."""
    try:
        return execute_who_knows(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("who_knows failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@tools_router.post("/page-rank", response_model=PageRankOutput)
def tool_page_rank(payload: PageRankInput) -> PageRankOutput:
    """Calculates structural centrality across the module graph using native PageRank."""
    try:
        return execute_page_rank(payload)
    except Exception as e:
        logger.error("page_rank failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@tools_router.post("/simulate", response_model=SimulationResult)
def tool_simulate_removal(payload: SimulateRemoveModuleInput) -> SimulationResult:
    """Runs isolated counterfactual module removal in a cloned graph."""
    try:
        return execute_simulate_remove_module(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("simulation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@tools_router.post("/security-triage", response_model=SecurityTriageOutput)
async def tool_security_triage(payload: SecurityTriageInput) -> SecurityTriageOutput:
    """Executes dependency security triage against public OSV vulnerability evidence."""
    try:
        return await execute_security_triage(payload)
    except Exception as e:
        logger.error("security_triage failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@tools_router.post("/investigate-fraud", response_model=FraudInvestigationOutput)
def tool_investigate_fraud(payload: FraudInvestigationInput) -> FraudInvestigationOutput:
    """Executes graph traversal on isolated synthetic fraud demonstration graph."""
    try:
        return execute_investigate_fraud(payload)
    except Exception as e:
        logger.error("investigate_fraud failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get("/subgraph", response_model=SubgraphResponse)
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


class RecentInvestigationItem(BaseModel):
    investigation_id: str
    question: str
    target_module_id: Optional[str] = None
    status: str
    summary: Optional[str] = None
    verification_status: Optional[str] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None
    investigation_mode: str = "codebase_walkthrough"
    repository_id: str = "repo:local_nexusact"
    graph_name: str = "nexusact_main"
    commit_sha: Optional[str] = None


class RecentInvestigationsResponse(BaseModel):
    investigations: List[RecentInvestigationItem]
    total: int


@router.get(
    "/recent",
    response_model=RecentInvestigationsResponse,
    summary="Get recent investigations across repository graphs",
)
def get_recent_investigations(
    limit: int = Query(default=15, ge=1, le=50),
    repo_id: Optional[str] = Query(default=None),
) -> RecentInvestigationsResponse:
    """Retrieves real recent completed investigations stored in FalkorDB graph memory."""
    all_items: List[RecentInvestigationItem] = []
    seen_ids = set()

    # Determine graphs to scan: if repo_id specified, inspect its graph; otherwise inspect registered graphs
    target_graphs: List[str] = []
    if repo_id:
        rec = repo_registry.get_repository(repo_id)
        if rec and rec.graph_name:
            target_graphs.append(rec.graph_name)
    else:
        for r in repo_registry.list_repositories():
            if r.graph_name and r.graph_name not in target_graphs:
                target_graphs.append(r.graph_name)
        if "nexusact_main" not in target_graphs:
            target_graphs.append("nexusact_main")
        if "nexusact_fraud_demo" not in target_graphs:
            target_graphs.append("nexusact_fraud_demo")

    query_str = """
    MATCH (inv:Investigation)
    RETURN inv.id, inv.question, inv.target_module_id, inv.status, inv.summary,
           inv.verification_status, inv.created_at, inv.finished_at,
           inv.investigation_mode, inv.repository_id, inv.graph_name, inv.commit_sha
    ORDER BY inv.created_at DESC
    LIMIT $limit
    """

    for g_name in target_graphs:
        try:
            rows = graph_client.query(query_str, params={"limit": limit}, graph_name=g_name)
            for row in rows:
                inv_id = str(row[0]) if row[0] else ""
                if not inv_id or inv_id in seen_ids:
                    continue
                seen_ids.add(inv_id)

                all_items.append(
                    RecentInvestigationItem(
                        investigation_id=inv_id,
                        question=str(row[1]) if row[1] else "",
                        target_module_id=str(row[2]) if row[2] else None,
                        status=str(row[3]) if row[3] else "COMPLETED",
                        summary=str(row[4]) if row[4] else None,
                        verification_status=str(row[5]) if row[5] else None,
                        created_at=str(row[6]) if row[6] else None,
                        finished_at=str(row[7]) if row[7] else None,
                        investigation_mode=str(row[8]) if row[8] else "codebase_walkthrough",
                        repository_id=str(row[9]) if row[9] else (repo_id or "repo:local_nexusact"),
                        graph_name=str(row[10]) if row[10] else g_name,
                        commit_sha=str(row[11]) if row[11] else None,
                    )
                )
        except Exception as e:
            logger.debug("Graph %s has no investigations or query skipped: %s", g_name, e)

    # Sort descending by created_at (or finished_at)
    all_items.sort(key=lambda x: x.created_at or x.finished_at or "", reverse=True)
    selected_items = all_items[:limit]

    return RecentInvestigationsResponse(
        investigations=selected_items,
        total=len(selected_items),
    )


# ── Phase 23: Simulation, Reviewers, and Chat Assistant Endpoints ─────────────


class SimulationCandidate(BaseModel):
    id: str
    name: str
    path: str
    in_degree: int
    out_degree: int
    is_entrypoint: bool = False


class SimulationCandidatesResponse(BaseModel):
    repo_id: str
    graph_name: str
    candidates: List[SimulationCandidate] = Field(default_factory=list)
    total: int


class SimulateModulePayload(BaseModel):
    repo_id: Optional[str] = None
    target_module_id: str
    graph_name: Optional[str] = None
    commit_sha: Optional[str] = None


class SimulationEndpointResponse(BaseModel):
    simulation: SimulationResult
    explanation: PanelExplanationResponse


class ReviewerResponseItem(BaseModel):
    person_id: str
    name: str
    email: str
    commits_count: int
    files_touched_count: int
    composite_score: float
    rank: int
    rationale: str
    is_lead: bool = False
    last_touch_date: Optional[str] = None
    touched_files: List[str] = Field(default_factory=list)
    relevant_commits: List[str] = Field(default_factory=list)


class ReviewersQueryResponse(BaseModel):
    repo_id: str
    graph_name: str
    target_module_id: Optional[str] = None
    candidates: List[ReviewerResponseItem] = Field(default_factory=list)
    total_repo_authors: int = 0
    has_explicit_reviews: bool = False
    scoring_formula: str = "composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews"
    explanation: PanelExplanationResponse


def _resolve_repo_and_graph(repo_id: Optional[str], graph_name: Optional[str]) -> tuple[str, str]:
    """Resolves repo_id and graph_name from registry with safe defaults."""
    resolved_repo = repo_id or "repo:local_nexusact"
    rec = repo_registry.get_repository(resolved_repo)
    if rec and rec.graph_name:
        return resolved_repo, rec.graph_name
    if graph_name:
        return resolved_repo, graph_name
    return resolved_repo, "nexusact_main"


@router.get(
    "/simulation-candidates",
    response_model=SimulationCandidatesResponse,
    summary="Get candidate modules in active graph available for counterfactual simulation",
)
def get_simulation_candidates(
    repo_id: Optional[str] = Query(default=None),
    graph_name: Optional[str] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
) -> SimulationCandidatesResponse:
    """Queries candidate modules from FalkorDB with in-degree and out-degree connectivity metrics."""
    resolved_repo, target_graph = _resolve_repo_and_graph(repo_id, graph_name)
    candidates: List[SimulationCandidate] = []

    cypher = """
    MATCH (m:Module)
    OPTIONAL MATCH (caller:Module)-[:DEPENDS_ON]->(m)
    OPTIONAL MATCH (m)-[:DEPENDS_ON]->(dep:Module)
    RETURN m.id AS id, m.name AS name, m.path AS path,
           count(DISTINCT caller) AS in_degree,
           count(DISTINCT dep) AS out_degree
    ORDER BY in_degree DESC, out_degree DESC
    LIMIT $limit
    """
    try:
        rows = graph_client.query(cypher, params={"limit": limit}, graph_name=target_graph)
        for r in rows:
            mid = str(r[0]) if r[0] else ""
            mname = str(r[1]) if r[1] else mid
            mpath = str(r[2]) if r[2] else ""
            in_deg = int(r[3]) if r[3] is not None else 0
            out_deg = int(r[4]) if r[4] is not None else 0

            candidates.append(
                SimulationCandidate(
                    id=mid,
                    name=mname,
                    path=mpath,
                    in_degree=in_deg,
                    out_degree=out_deg,
                    is_entrypoint=(in_deg == 0 and out_deg > 0),
                )
            )
    except Exception as e:
        logger.warning("Failed to fetch simulation candidates on graph %s: %s", target_graph, e)

    return SimulationCandidatesResponse(
        repo_id=resolved_repo,
        graph_name=target_graph,
        candidates=candidates,
        total=len(candidates),
    )


@router.post(
    "/simulate",
    response_model=SimulationEndpointResponse,
    summary="Execute real FalkorDB isolated graph counterfactual scenario simulation",
)
async def run_scenario_simulation(payload: SimulateModulePayload) -> SimulationEndpointResponse:
    """Executes counterfactual removal of target module in an isolated scenario graph clone."""
    resolved_repo, target_graph = _resolve_repo_and_graph(payload.repo_id, payload.graph_name)

    try:
        sim_res = execute_simulate_remove_module(
            SimulateRemoveModuleInput(
                module_identifier=payload.target_module_id,
                graph_name=target_graph,
            )
        )

        sim_summary = {
            "has_run": True,
            "target_module_id": sim_res.target_module_name or sim_res.target_module_id,
            "baseline_paths": sim_res.baseline_paths_count,
            "disrupted_paths": sim_res.disappeared_paths_count,
            "surviving_paths": sim_res.surviving_paths_count,
            "blast_radius": sim_res.blast_radius_score,
            "newly_isolated_modules": sim_res.newly_isolated_modules,
        }

        explanation = await generate_panel_explanation(
            PanelExplanationRequest(
                investigation_id=f"sim_{sim_res.scenario_id}",
                panel_id="simulation",
                question=f"What is the architectural blast radius of removing '{payload.target_module_id}'?",
                target_id=sim_res.target_module_name or sim_res.target_module_id,
                repo_id=resolved_repo,
                commit_sha=payload.commit_sha,
                data_summary=sim_summary,
            )
        )

        return SimulationEndpointResponse(simulation=sim_res, explanation=explanation)
    except Exception as e:
        logger.error("Simulation failed for %s on %s: %s", payload.target_module_id, target_graph, e)
        raise HTTPException(status_code=500, detail=f"Scenario simulation failed: {str(e)}")


@router.get(
    "/reviewers",
    response_model=ReviewersQueryResponse,
    summary="Query contributor and reviewer intelligence grounded in Git commit history",
)
async def get_reviewers_and_authors(
    repo_id: Optional[str] = Query(default=None),
    target_module_id: Optional[str] = Query(default=None),
    graph_name: Optional[str] = Query(default=None),
    commit_sha: Optional[str] = Query(default=None),
) -> ReviewersQueryResponse:
    """Retrieves ranked authors and reviewers from real Git history graph edges."""
    resolved_repo, target_graph = _resolve_repo_and_graph(repo_id, graph_name)
    candidates: List[ReviewerResponseItem] = []
    total_repo_authors = 0
    has_explicit_reviews = False

    # 1. Total authors across repository
    try:
        cnt_res = graph_client.query(
            "MATCH (p:Person)-[:AUTHORED]->(:Commit) RETURN count(DISTINCT p) AS total",
            graph_name=target_graph,
        )
        if cnt_res and len(cnt_res) > 0 and cnt_res[0][0]:
            total_repo_authors = int(cnt_res[0][0])
    except Exception as e:
        logger.debug("Failed counting authors on %s: %s", target_graph, e)

    # 2. Check for explicit REVIEWS edges
    try:
        rev_res = graph_client.query(
            "MATCH ()-[r:REVIEWS]->() RETURN count(r) AS reviews_count",
            graph_name=target_graph,
        )
        if rev_res and len(rev_res) > 0 and rev_res[0][0]:
            has_explicit_reviews = int(rev_res[0][0]) > 0
    except Exception as e:
        logger.debug("Failed checking reviews edges on %s: %s", target_graph, e)

    # 3. Retrieve candidates for target_module_id or repo-wide
    if target_module_id:
        try:
            who_output = execute_who_knows(
                WhoKnowsInput(
                    module_identifier=target_module_id,
                    graph_name=target_graph,
                )
            )
            for idx, cand in enumerate(who_output.candidates):
                candidates.append(
                    ReviewerResponseItem(
                        person_id=cand.person_id,
                        name=cand.name,
                        email=cand.email,
                        commits_count=cand.breakdown.commits_count,
                        files_touched_count=cand.breakdown.files_touched_count,
                        composite_score=cand.composite_score,
                        rank=cand.rank,
                        rationale=cand.rationale,
                        is_lead=(idx == 0),
                    )
                )
        except Exception as e:
            logger.debug("Targeted who_knows search yielded no direct matches for %s: %s", target_module_id, e)

    # If no module candidates found or no target module provided, query top authors repo-wide
    if not candidates and total_repo_authors > 0:
        author_query = """
        MATCH (p:Person)-[:AUTHORED]->(c:Commit)
        OPTIONAL MATCH (c)-[:TOUCHES]->(f:File)
        RETURN p.id AS person_id,
               p.name AS name,
               p.email AS email,
               count(DISTINCT f.id) AS files_touched,
               count(DISTINCT c.id) AS commit_count,
               max(c.timestamp) AS last_commit_time
        ORDER BY commit_count DESC, files_touched DESC
        LIMIT 15
        """
        try:
            rows = graph_client.query(author_query, graph_name=target_graph)
            max_commits = max([int(r[4]) for r in rows if r[4]] or [1])
            for idx, r in enumerate(rows):
                pid = str(r[0]) if r[0] else f"person_{idx}"
                name = str(r[1]) if r[1] else pid
                email = str(r[2]) if r[2] else ""
                files_cnt = int(r[3]) if r[3] is not None else 0
                commit_cnt = int(r[4]) if r[4] is not None else 0
                last_time = str(r[5]) if r[5] else None

                # Compute normalized score
                norm_score = round(min(1.0, commit_cnt / max_commits), 2)
                candidates.append(
                    ReviewerResponseItem(
                        person_id=pid,
                        name=name,
                        email=email,
                        commits_count=commit_cnt,
                        files_touched_count=files_cnt,
                        composite_score=norm_score,
                        rank=idx + 1,
                        rationale=(
                            f"Repository contributor with {commit_cnt} recorded commits touching {files_cnt} files."
                        ),
                        is_lead=(idx == 0),
                        last_touch_date=last_time,
                    )
                )
        except Exception as e:
            logger.warning("Repo-wide author query failed on %s: %s", target_graph, e)

    # 4. Generate structured explanation
    exp_data = {
        "candidates": [c.model_dump() for c in candidates],
        "total_repo_authors": total_repo_authors,
        "has_explicit_reviews": has_explicit_reviews,
        "target_module_id": target_module_id,
    }
    explanation = await generate_panel_explanation(
        PanelExplanationRequest(
            investigation_id=f"rev_{resolved_repo}_{target_module_id or 'all'}",
            panel_id="reviewers",
            question="Who are the qualified contributors and code reviewers?",
            target_id=target_module_id,
            repo_id=resolved_repo,
            commit_sha=commit_sha,
            data_summary=exp_data,
        )
    )

    return ReviewersQueryResponse(
        repo_id=resolved_repo,
        graph_name=target_graph,
        target_module_id=target_module_id,
        candidates=candidates,
        total_repo_authors=total_repo_authors,
        has_explicit_reviews=has_explicit_reviews,
        scoring_formula="composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews",
        explanation=explanation,
    )


@router.post(
    "/chat",
    response_model=ChatInvestigationResponse,
    summary="Ask natural language questions answered via real FalkorDB Cypher execution and model reasoning",
)
async def chat_investigation(payload: ChatInvestigationRequest) -> ChatInvestigationResponse:
    """Answers engineering or dataset questions using graph schema discovery and read-only Cypher."""
    try:
        service = GraphChatService()
        return await service.answer_question(payload)
    except Exception as e:
        logger.error("Chat investigation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Graph Chat Assistant failed: {str(e)}")
