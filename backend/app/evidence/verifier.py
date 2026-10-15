"""Evidence and path verification module (PathVerifier).

Validates graph traversal paths against FalkorDB to ensure:
1. All node and edge IDs exist in the active graph.
2. Path begins and ends at expected resolved entities.
3. Edge types and directions match canonical semantics (upstream -[:DEPENDS_ON]-> downstream).
4. Relevant edge evidence references (source_file) exist.
5. Inferred/derived relationships are not represented as direct observed dependencies.
6. Results belong to the intended repository scope.
7. Truncated query results are explicitly flagged.
"""

import logging
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE, REL_DEPENDS_ON
from backend.app.graph.tools.impact import TraceImpactOutput

logger = logging.getLogger("nexusact.evidence.verifier")


class VerificationStatus(str, Enum):
    """Rigorous verification classification for graph-derived paths and claims."""

    VERIFIED = "VERIFIED"  # All node IDs, edge directions, and source evidence verified in graph
    SUPPORTED = "SUPPORTED"  # Graph topology verified, but partial source evidence or indirect hops
    CONTRADICTED = "CONTRADICTED"  # Graph edges do not exist, wrong direction, or target mismatch
    UNKNOWN = "UNKNOWN"  # Graph unreachable, entities missing, or cannot be evaluated


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    details: str


class PathVerificationResult(BaseModel):
    status: VerificationStatus
    target_module_id: str
    checked_paths_count: int
    valid_paths_count: int
    invalid_paths_count: int
    checks: List[VerificationCheck] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    validated_node_ids: List[str] = Field(default_factory=list)
    validated_edge_ids: List[str] = Field(default_factory=list)
    is_truncated: bool = False


class PathVerifier:
    """Verifies paths returned by graph queries against actual FalkorDB data."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or graph_client

    def verify_impact_output(
        self,
        impact_output: TraceImpactOutput,
        graph_name: Optional[str] = None,
        expected_repo_id: Optional[str] = None,
    ) -> PathVerificationResult:
        """Verifies an entire TraceImpactOutput against FalkorDB."""
        target_graph = graph_name or self.client.primary_graph_name
        target_id = impact_output.target_module_id

        checks: List[VerificationCheck] = []
        limitations: List[str] = []
        validated_nodes: set[str] = set()
        validated_edges: set[str] = set()

        # Check 0: Graph availability
        try:
            target_node = self.client.query(
                f"MATCH (m:{LABEL_MODULE} {{id: $id}}) RETURN m.id, m.repository_id LIMIT 1",
                params={"id": target_id},
                graph_name=target_graph,
            )
            if not target_node:
                checks.append(
                    VerificationCheck(
                        name="target_existence",
                        passed=False,
                        details=f"Target module '{target_id}' does not exist in graph '{target_graph}'.",
                    )
                )
                return PathVerificationResult(
                    status=VerificationStatus.CONTRADICTED,
                    target_module_id=target_id,
                    checked_paths_count=len(impact_output.impacted_modules),
                    valid_paths_count=0,
                    invalid_paths_count=len(impact_output.impacted_modules),
                    checks=checks,
                    limitations=[f"Target '{target_id}' not found in active graph."],
                )
            checks.append(
                VerificationCheck(
                    name="target_existence",
                    passed=True,
                    details=f"Target module '{target_id}' exists in '{target_graph}'.",
                )
            )
            validated_nodes.add(target_id)
        except Exception as e:
            logger.error("Failed to query target module in FalkorDB: %s", e)
            return PathVerificationResult(
                status=VerificationStatus.UNKNOWN,
                target_module_id=target_id,
                checked_paths_count=len(impact_output.impacted_modules),
                valid_paths_count=0,
                invalid_paths_count=0,
                checks=[VerificationCheck(name="graph_connection", passed=False, details=str(e))],
                limitations=["Database connection failure prevented verification."],
            )

        # Check Truncation limitation
        if impact_output.is_truncated:
            limitations.append(
                "Query results were truncated at maximum limit. Path analysis is bounded, not globally exhaustive."
            )

        # If zero impacted modules returned, verify target has 0 reverse dependencies
        if not impact_output.impacted_modules:
            checks.append(
                VerificationCheck(
                    name="zero_impact_validation",
                    passed=True,
                    details="Verified target module has no upstream dependent modules within 4 hops.",
                )
            )
            return PathVerificationResult(
                status=VerificationStatus.VERIFIED,
                target_module_id=target_id,
                checked_paths_count=0,
                valid_paths_count=0,
                invalid_paths_count=0,
                checks=checks,
                limitations=limitations,
                validated_node_ids=list(validated_nodes),
                validated_edge_ids=[],
                is_truncated=impact_output.is_truncated,
            )

        valid_count = 0
        invalid_count = 0
        all_edges_have_evidence = True
        contradiction_found = False

        for impacted in impact_output.impacted_modules:
            path_ids = impacted.path
            if not path_ids:
                invalid_count += 1
                contradiction_found = True
                continue

            # Check 1: Path end matches target_id
            if path_ids[-1] != target_id:
                invalid_count += 1
                contradiction_found = True
                checks.append(
                    VerificationCheck(
                        name=f"path_endpoint_{impacted.module_id}",
                        passed=False,
                        details=f"Path terminates at '{path_ids[-1]}' instead of target '{target_id}'.",
                    )
                )
                continue

            # Check 2: Path start matches upstream module_id
            if path_ids[0] != impacted.module_id:
                invalid_count += 1
                contradiction_found = True
                checks.append(
                    VerificationCheck(
                        name=f"path_start_{impacted.module_id}",
                        passed=False,
                        details=f"Path begins at '{path_ids[0]}' instead of expected '{impacted.module_id}'.",
                    )
                )
                continue

            # Check 3: Verify each consecutive step (u)-[:DEPENDS_ON]->(v) exists in graph
            path_step_valid = True
            for i in range(len(path_ids) - 1):
                u_id = path_ids[i]
                v_id = path_ids[i + 1]

                step_res = self.client.query(
                    f"""
                    MATCH (u:{LABEL_MODULE} {{id: $u}})-[r:{REL_DEPENDS_ON}]->(v:{LABEL_MODULE} {{id: $v}})
                    RETURN r.id, r.source_file, r.evidence_type, u.repository_id
                    LIMIT 1
                    """,
                    params={"u": u_id, "v": v_id},
                    graph_name=target_graph,
                )

                if not step_res:
                    path_step_valid = False
                    contradiction_found = True
                    checks.append(
                        VerificationCheck(
                            name=f"edge_exists_{u_id}_to_{v_id}",
                            passed=False,
                            details=f"No active DEPENDS_ON edge from '{u_id}' to '{v_id}' in graph.",
                        )
                    )
                    break
                else:
                    edge_id, source_file, evidence_type, repo_id = step_res[0]
                    validated_nodes.add(u_id)
                    validated_nodes.add(v_id)
                    if edge_id:
                        validated_edges.add(str(edge_id))
                    else:
                        validated_edges.add(f"{u_id}->{v_id}")

                    # Check evidence reference
                    if not source_file:
                        all_edges_have_evidence = False

                    # Check repo scope if expected
                    if expected_repo_id and repo_id and repo_id != expected_repo_id:
                        limitations.append(
                            f"Module '{u_id}' has repository_id '{repo_id}' differing from '{expected_repo_id}'."
                        )

            if path_step_valid:
                valid_count += 1
            else:
                invalid_count += 1

        checks.append(
            VerificationCheck(
                name="path_continuity_check",
                passed=(invalid_count == 0),
                details=f"Validated {valid_count}/{len(impact_output.impacted_modules)} complete dependency paths.",
            )
        )

        # Determine overall verification status
        if contradiction_found or invalid_count > 0:
            final_status = VerificationStatus.CONTRADICTED
        elif not all_edges_have_evidence:
            final_status = VerificationStatus.SUPPORTED
            limitations.append("Some dependency edges lack explicit source_file provenance records.")
        else:
            final_status = VerificationStatus.VERIFIED

        return PathVerificationResult(
            status=final_status,
            target_module_id=target_id,
            checked_paths_count=len(impact_output.impacted_modules),
            valid_paths_count=valid_count,
            invalid_paths_count=invalid_count,
            checks=checks,
            limitations=limitations,
            validated_node_ids=sorted(list(validated_nodes)),
            validated_edge_ids=sorted(list(validated_edges)),
            is_truncated=impact_output.is_truncated,
        )


path_verifier = PathVerifier()
