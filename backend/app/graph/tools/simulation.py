"""Counterfactual simulation tool: isolated module removal using GRAPH.COPY."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import PROTECTED_GRAPHS, FalkorDBClient, graph_client
from backend.app.graph.tools.impact import TraceImpactInput, execute_trace_impact, resolve_module_id

logger = logging.getLogger("nexusact.tools.simulation")


class DisappearedPath(BaseModel):
    dependent_module_id: str
    dependent_module_name: str
    broken_path: List[str]


class SimulationResult(BaseModel):
    scenario_id: str
    target_module_id: str
    target_module_name: str
    disappeared_paths_count: int
    disappeared_paths: List[DisappearedPath] = Field(default_factory=list)
    disconnected_modules: List[str] = Field(default_factory=list, description="Modules that lost all dependencies")
    surviving_modules_count: int
    surviving_edges_count: int
    blast_radius_score: float = Field(..., description="Proportion of modules affected (0.0 to 1.0)")
    disclaimer: str = (
        "Simulation prediction is derived from static dependency topology. "
        "It indicates topological disruption, not verified runtime build or test failure."
    )


class SimulateRemoveModuleInput(BaseModel):
    module_identifier: str = Field(..., description="Module ID or name to hypothetically remove")
    graph_name: Optional[str] = Field(default=None, description="Source graph to clone from (defaults to primary)")


def execute_simulate_remove_module(
    payload: SimulateRemoveModuleInput,
    client: Optional[FalkorDBClient] = None,
) -> SimulationResult:
    """Clones the graph, removes the target module, computes the blast radius, and cleans up."""
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

    # 1. Baseline Analysis on source graph
    baseline_impact = execute_trace_impact(
        TraceImpactInput(module_identifier=resolved_id, max_depth=4, limit=100, graph_name=source_graph),
        client=cli,
    )

    baseline_diag = cli.get_graph_diagnostics(source_graph)
    baseline_node_count = baseline_diag.get("node_count", 0)

    # 2. Ephemeral Scenario Graph Name
    scenario_suffix = uuid.uuid4().hex[:8]
    scenario_graph = f"scenario_sim_{scenario_suffix}"
    scenario_id = f"scen:{scenario_suffix}"

    try:
        # 3. Clone graph via GRAPH.COPY
        cli.copy_graph(source_graph, scenario_graph)

        # 4. Detach delete target module in the copy ONLY
        cli.query(
            "MATCH (m:Module {id: $id}) DETACH DELETE m",
            params={"id": resolved_id},
            graph_name=scenario_graph,
        )

        # 5. Measure surviving metrics in scenario copy
        scenario_diag = cli.get_graph_diagnostics(scenario_graph)
        surviving_nodes = scenario_diag.get("node_count", 0)
        surviving_edges = scenario_diag.get("edge_count", 0)

        # Check which modules have 0 remaining outgoing dependencies in the scenario
        disconnected_res = cli.query(
            """
            MATCH (m:Module)
            WHERE NOT (m)-[:DEPENDS_ON]->()
            RETURN m.id
            """,
            graph_name=scenario_graph,
        )
        disconnected = [row[0] for row in disconnected_res if row]

        # 6. Map disappeared paths
        disappeared: List[DisappearedPath] = []
        for imp in baseline_impact.impacted_modules:
            disappeared.append(
                DisappearedPath(
                    dependent_module_id=imp.module_id,
                    dependent_module_name=imp.module_name,
                    broken_path=imp.path,
                )
            )

        blast_radius = round(len(disappeared) / float(baseline_node_count), 3) if baseline_node_count > 0 else 0.0

        sim_result = SimulationResult(
            scenario_id=scenario_id,
            target_module_id=resolved_id,
            target_module_name=mod_name,
            disappeared_paths_count=len(disappeared),
            disappeared_paths=disappeared,
            disconnected_modules=disconnected[:20],
            surviving_modules_count=surviving_nodes,
            surviving_edges_count=surviving_edges,
            blast_radius_score=blast_radius,
        )

        # 7. Record Scenario & ScenarioResult in main graph
        now_iso = datetime.now(timezone.utc).isoformat()
        cli.query(
            """
            MATCH (m:Module {id: $target_id})
            MERGE (sc:Scenario {id: $scen_id})
            SET sc.target_module = $target_id,
                sc.blast_radius = $blast,
                sc.disappeared_paths = $dis_count,
                sc.created_at = $ts
            MERGE (sc)-[:TARGETS]->(m)
            """,
            params={
                "scen_id": scenario_id,
                "target_id": resolved_id,
                "blast": blast_radius,
                "dis_count": len(disappeared),
                "ts": now_iso,
            },
            graph_name=source_graph,
        )

        return sim_result

    finally:
        # 8. Guaranteed Cleanup of temporary scenario graph
        if scenario_graph not in PROTECTED_GRAPHS:
            cli.delete_graph(scenario_graph, force=True)
            logger.info("Cleaned up temporary scenario graph: %s", scenario_graph)
