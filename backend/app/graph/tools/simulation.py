"""Counterfactual simulation tool: genuine before/after comparison using GRAPH.COPY.

Counterfactual question:
  "If module T is removed, which upstream modules lose at least one route to T's
   dependencies, and which still have an alternate route?"

Semantics:
  T has direct dependencies D1, D2, ...
  For each Di, there exist upstream modules that have at least one path to Di.
  Some of those paths route THROUGH T; others do not.

  An upstream module U is "affected" by removing T if ANY of its paths to Di
  routed through T.

  After removing T:
  - If U still has at least one path to Di (not through T) → SURVIVING (has alternate route)
  - If U has NO path to Di anymore → BROKEN (all routes went through T)

  Note: U is reported ONCE per (upstream, dep) pair.

blast_radius = |broken_upstreams| / |affected_upstreams|
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.graph.client import PROTECTED_GRAPHS, FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.impact import resolve_module_id

logger = logging.getLogger("nexusact.tools.simulation")


# ── Data models ─────────────────────────────────────────────────────────────────


class DisappearedPath(BaseModel):
    dependent_module_id: str
    dependent_module_name: str
    broken_path: List[str]  # One representative broken path
    hops: int


class SurvivingPath(BaseModel):
    dependent_module_id: str
    dependent_module_name: str
    surviving_path: List[str]  # Alternate surviving path (verified in scenario copy)
    hops: int


class SimulationResult(BaseModel):
    scenario_id: str
    target_module_id: str
    target_module_name: str

    baseline_paths_count: int = Field(
        description="Number of (upstream_module, dep) pairs where at least one path routed through the target"
    )
    baseline_node_count: int

    disappeared_paths_count: int
    disappeared_paths: List[DisappearedPath] = Field(default_factory=list)
    surviving_paths_count: int
    surviving_paths: List[SurvivingPath] = Field(default_factory=list)

    newly_isolated_modules: List[str] = Field(
        default_factory=list,
        description="Callers of target that now have zero outgoing DEPENDS_ON edges in the scenario copy",
    )

    surviving_modules_count: int
    surviving_edges_count: int

    blast_radius_score: float = Field(
        ...,
        description=(
            "broken_pairs / affected_pairs. 0.0 = all affected upstreams have alternate routes; 1.0 = all broken."
        ),
    )
    is_incomplete: bool = Field(
        default=False,
        description="True if path queries were truncated at limit.",
    )
    disclaimer: str = (
        "Simulation is derived from static dependency topology. "
        "blast_radius_score = broken_pairs / affected_pairs. "
        "Indicates topological disruption, not verified runtime build or test failure."
    )


class SimulateRemoveModuleInput(BaseModel):
    module_identifier: str = Field(..., description="Module ID or name to hypothetically remove")
    graph_name: Optional[str] = Field(default=None)


# ── Helpers ──────────────────────────────────────────────────────────────────────


def _get_direct_dependencies(client: FalkorDBClient, target_id: str, graph_name: str) -> List[str]:
    rows = client.query(
        f"MATCH (t:{LABEL_MODULE} {{id: $tid}})-[:{REL_DEPENDS_ON}]->(dep:{LABEL_MODULE}) RETURN dep.id",
        params={"tid": target_id},
        graph_name=graph_name,
    )
    return [row[0] for row in rows if row]


def _get_direct_callers(client: FalkorDBClient, target_id: str, graph_name: str) -> Dict[str, str]:
    cypher = (
        f"MATCH (caller:{LABEL_MODULE})-[:{REL_DEPENDS_ON}]->(t:{LABEL_MODULE} {{id: $tid}}) "
        "RETURN caller.id, caller.name"
    )
    rows = client.query(
        cypher,
        params={"tid": target_id},
        graph_name=graph_name,
    )
    return {row[0]: (row[1] or row[0]) for row in rows if row}


def _collect_all_paths_to_dep(
    client: FalkorDBClient,
    dep_id: str,
    graph_name: str,
    limit: int = 300,
) -> List[Dict]:
    """
    Collect ALL paths (up to limit) from any upstream module to dep_id.
    Returns list of {upstream_id, upstream_name, path_ids, hops}.
    All paths are returned — not deduplicated by upstream_id.
    This is necessary to detect both direct and billing-routed paths.
    """
    rows = client.query(
        f"""
        MATCH p = (upstream:{LABEL_MODULE})-[:{REL_DEPENDS_ON}*1..4]->(dep:{LABEL_MODULE} {{id: $did}})
        WHERE upstream.id <> dep.id
        RETURN upstream.id, upstream.name, [n IN nodes(p) | n.id], length(p)
        ORDER BY length(p) ASC
        LIMIT $lim
        """,
        params={"did": dep_id, "lim": limit},
        graph_name=graph_name,
    )
    result = []
    for row in rows:
        result.append(
            {
                "upstream_id": row[0],
                "upstream_name": row[1] or row[0],
                "path_ids": [str(p) for p in row[2]] if isinstance(row[2], list) else [],
                "hops": row[3],
            }
        )
    return result


def _collect_shortest_path_to_dep(
    client: FalkorDBClient,
    dep_id: str,
    graph_name: str,
    limit: int = 200,
) -> Dict[str, Tuple[List[str], int]]:
    """
    Returns {upstream_id: (path_ids, hops)} with shortest path per upstream.
    """
    rows = client.query(
        f"""
        MATCH p = (upstream:{LABEL_MODULE})-[:{REL_DEPENDS_ON}*1..4]->(dep:{LABEL_MODULE} {{id: $did}})
        WHERE upstream.id <> dep.id
        RETURN upstream.id, [n IN nodes(p) | n.id], length(p)
        ORDER BY length(p) ASC
        LIMIT $lim
        """,
        params={"did": dep_id, "lim": limit},
        graph_name=graph_name,
    )
    result: Dict[str, Tuple[List[str], int]] = {}
    for row in rows:
        up_id = row[0]
        if up_id not in result:
            result[up_id] = (
                [str(p) for p in row[1]] if isinstance(row[1], list) else [],
                row[2],
            )
    return result


def _path_contains_as_intermediate(path_ids: List[str], node_id: str) -> bool:
    """True if node_id appears in the path as a middle node (not source, not destination)."""
    if len(path_ids) < 3:
        return False
    return node_id in path_ids[1:-1]


def _newly_isolated_callers(
    client: FalkorDBClient,
    caller_ids: List[str],
    scenario_graph: str,
) -> List[str]:
    isolated = []
    for cid in caller_ids:
        rows = client.query(
            f"MATCH (m:{LABEL_MODULE} {{id: $cid}})-[out:{REL_DEPENDS_ON}]->() RETURN count(out)",
            params={"cid": cid},
            graph_name=scenario_graph,
        )
        if rows and rows[0][0] == 0:
            isolated.append(cid)
    return isolated


# ── Main ─────────────────────────────────────────────────────────────────────────


def execute_simulate_remove_module(
    payload: SimulateRemoveModuleInput,
    client: Optional[FalkorDBClient] = None,
) -> SimulationResult:
    """
    Genuine counterfactual: clone graph, remove target, compare reachability.
    An upstream module U is "affected" if it had at least one path to a target dependency
    that routed through the target.  After removing the target, if U has NO alternate path
    to that dependency → BROKEN.  If U still has a path → SURVIVING.
    """
    cli = client or graph_client
    source_graph = payload.graph_name or cli.primary_graph_name

    resolved_id = resolve_module_id(cli, payload.module_identifier, graph_name=source_graph)
    if not resolved_id:
        raise ValueError(f"Module '{payload.module_identifier}' could not be resolved.")

    mod_name_res = cli.query(
        "MATCH (m:Module {id: $id}) RETURN m.name LIMIT 1",
        params={"id": resolved_id},
        graph_name=source_graph,
    )
    mod_name = mod_name_res[0][0] if mod_name_res else resolved_id

    # ── 1. Baseline ────────────────────────────────────────────────────────────
    baseline_diag = cli.get_graph_diagnostics(source_graph)
    baseline_node_count = baseline_diag.get("node_count", 0)

    dep_ids = _get_direct_dependencies(cli, resolved_id, source_graph)
    direct_callers = _get_direct_callers(cli, resolved_id, source_graph)

    LIMIT = 300

    # For each dependency of target, collect ALL paths.
    # Identify (upstream, dep) pairs where ANY path routes through the target.
    # These are "affected" pairs.
    # Also record ONE representative broken path per pair (longest one through target).
    affected: Dict[Tuple[str, str], Dict] = {}  # (up_id, dep_id) → record
    is_incomplete = False

    for dep_id in dep_ids:
        all_paths = _collect_all_paths_to_dep(cli, dep_id, source_graph, limit=LIMIT)
        if len(all_paths) >= LIMIT:
            is_incomplete = True

        for rec in all_paths:
            up_id = rec["upstream_id"]
            path_ids = rec["path_ids"]
            key = (up_id, dep_id)
            if _path_contains_as_intermediate(path_ids, resolved_id):
                # This upstream has at least one path through the target
                if key not in affected:
                    affected[key] = {
                        "upstream_id": up_id,
                        "upstream_name": rec["upstream_name"],
                        "dep_id": dep_id,
                        "broken_path": path_ids,  # representative broken path
                        "hops": rec["hops"],
                    }

    baseline_paths_count = len(affected)

    # ── 2. Clone + remove ─────────────────────────────────────────────────────
    scenario_suffix = uuid.uuid4().hex[:8]
    scenario_graph = f"scenario_sim_{scenario_suffix}"
    scenario_id = f"scen:{scenario_suffix}"

    try:
        cli.copy_graph(source_graph, scenario_graph)
        cli.query(
            "MATCH (m:Module {id: $id}) DETACH DELETE m",
            params={"id": resolved_id},
            graph_name=scenario_graph,
        )

        # ── 3. Scenario reachability (shortest path per upstream per dep) ─────
        scenario_reach: Dict[str, Dict[str, Tuple[List[str], int]]] = {}
        for dep_id in dep_ids:
            scenario_reach[dep_id] = _collect_shortest_path_to_dep(cli, dep_id, scenario_graph, limit=LIMIT)

        # ── 4. Compare affected pairs ──────────────────────────────────────────
        disappeared: List[DisappearedPath] = []
        surviving: List[SurvivingPath] = []

        for (up_id, dep_id), rec in affected.items():
            if up_id in scenario_reach.get(dep_id, {}):
                # Still reachable via an alternate route
                alt_path, alt_hops = scenario_reach[dep_id][up_id]
                surviving.append(
                    SurvivingPath(
                        dependent_module_id=up_id,
                        dependent_module_name=rec["upstream_name"],
                        surviving_path=alt_path,
                        hops=alt_hops,
                    )
                )
            else:
                disappeared.append(
                    DisappearedPath(
                        dependent_module_id=up_id,
                        dependent_module_name=rec["upstream_name"],
                        broken_path=rec["broken_path"],
                        hops=rec["hops"],
                    )
                )

        # ── 5. Newly isolated callers ──────────────────────────────────────────
        newly_isolated = _newly_isolated_callers(cli, list(direct_callers.keys()), scenario_graph)

        # ── 6. Scenario diagnostics ────────────────────────────────────────────
        scenario_diag = cli.get_graph_diagnostics(scenario_graph)
        surviving_nodes = scenario_diag.get("node_count", 0)
        surviving_edges = scenario_diag.get("edge_count", 0)

        # ── 7. Blast radius ────────────────────────────────────────────────────
        blast_radius = round(len(disappeared) / baseline_paths_count, 3) if baseline_paths_count > 0 else 0.0

        sim_result = SimulationResult(
            scenario_id=scenario_id,
            target_module_id=resolved_id,
            target_module_name=mod_name,
            baseline_paths_count=baseline_paths_count,
            baseline_node_count=baseline_node_count,
            disappeared_paths_count=len(disappeared),
            disappeared_paths=disappeared[:50],
            surviving_paths_count=len(surviving),
            surviving_paths=surviving[:50],
            newly_isolated_modules=newly_isolated[:20],
            surviving_modules_count=surviving_nodes,
            surviving_edges_count=surviving_edges,
            blast_radius_score=blast_radius,
            is_incomplete=is_incomplete,
        )

        # ── 8. Persist scenario record ─────────────────────────────────────────
        now_iso = datetime.now(timezone.utc).isoformat()
        cli.query(
            """
            MATCH (m:Module {id: $target_id})
            MERGE (sc:Scenario {id: $scen_id})
            SET sc.target_module = $target_id,
                sc.blast_radius = $blast,
                sc.baseline_paths = $b_total,
                sc.disappeared_paths = $dis_count,
                sc.surviving_paths = $surv_count,
                sc.created_at = $ts
            MERGE (sc)-[:TARGETS]->(m)
            """,
            params={
                "scen_id": scenario_id,
                "target_id": resolved_id,
                "blast": blast_radius,
                "b_total": baseline_paths_count,
                "dis_count": len(disappeared),
                "surv_count": len(surviving),
                "ts": now_iso,
            },
            graph_name=source_graph,
        )

        return sim_result

    finally:
        if scenario_graph not in PROTECTED_GRAPHS:
            deleted = cli.delete_graph(scenario_graph, force=True)
            if deleted:
                logger.info("Cleaned up temporary scenario graph: %s", scenario_graph)
            else:
                logger.warning("Failed to clean up scenario graph: %s", scenario_graph)
