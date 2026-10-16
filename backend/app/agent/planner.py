"""Adaptive Investigation Planner and Execution Loop.

Orchestrates multi-step, evidence-backed investigations using registered MCP tools:
1. Target resolution & plan generation.
2. Tool discovery from MCP interface.
3. Adaptive decision loop powered by configured model provider.
4. Path verification via PathVerifier.
5. FalkorDB persistence of Investigation and ToolInvocation records.
6. Structured issue proposal generation.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.agent.llm import BaseLLMProvider, LLMDecision, LLMToolCall, get_llm_provider
from backend.app.evidence.verifier import PathVerificationResult, PathVerifier
from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE
from backend.app.graph.tools.centrality import PageRankOutput
from backend.app.graph.tools.impact import (
    TraceImpactOutput,
    resolve_module_id,
)
from backend.app.graph.tools.neighborhood import GraphNeighborhoodOutput
from backend.app.graph.tools.resolve import (
    EntityResolutionOutput,
    ResolveEntityInput,
    execute_resolve_entity,
)
from backend.app.graph.tools.reviewers import WhoKnowsOutput
from backend.app.graph.tools.shortest_path import ShortestPathOutput
from backend.app.graph.tools.simulation import SimulationResult
from backend.app.sources.models import SourceMetadataOutput
from backend.app.sources.registry import repo_registry
from mcp_server.server import create_mcp_server

logger = logging.getLogger("nexusact.agent.planner")


class InvestigationStep(BaseModel):
    step_number: int
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    purpose: str = ""
    status: str = "COMPLETED"  # COMPLETED | FAILED | REJECTED
    result_summary: str = ""
    execution_time_ms: float = 0.0


class InvestigationReport(BaseModel):
    investigation_id: str
    question: str
    target_module_id: str
    target_module_name: str
    status: str = "COMPLETED"  # COMPLETED | AMBIGUOUS | UNRESOLVED | FAILED
    steps: List[InvestigationStep] = Field(default_factory=list)
    verification: Optional[PathVerificationResult] = None
    summary: str = ""
    impact_result: Optional[TraceImpactOutput] = None
    reviewer_result: Optional[WhoKnowsOutput] = None
    pagerank_result: Optional[PageRankOutput] = None
    simulation_result: Optional[SimulationResult] = None
    neighborhood_result: Optional[GraphNeighborhoodOutput] = None
    shortest_path_result: Optional[ShortestPathOutput] = None
    source_metadata_result: Optional[SourceMetadataOutput] = None
    action_proposal: Optional[Dict[str, Any]] = None
    ambiguity_candidates: Optional[List[Dict[str, Any]]] = None
    repository_id: Optional[str] = None
    graph_name: Optional[str] = None
    commit_sha: Optional[str] = None
    unresolved_reason: Optional[str] = None
    is_heuristic_fallback: bool = True
    budget_used: int = 0
    budget_remaining: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AdaptiveInvestigationAgent:
    """Bounded, adaptive agent that explores the graph using registered MCP tools."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        client: Optional[FalkorDBClient] = None,
        max_tool_budget: int = 5,
    ):
        self.llm = llm_provider or get_llm_provider()
        self.client = client or graph_client
        self.max_tool_budget = max(1, min(max_tool_budget, 8))
        self.mcp_server = create_mcp_server()
        self.verifier = PathVerifier(self.client)

    async def investigate(
        self,
        question: str,
        module_identifier: Optional[str] = None,
        repo_id: Optional[str] = None,
        graph_name: Optional[str] = None,
        custom_provider: Optional[BaseLLMProvider] = None,
    ) -> InvestigationReport:
        """Executes the full adaptive investigation workflow with multi-repository and NL target resolution."""
        target_graph = graph_name
        resolved_repo_id = repo_id
        if not target_graph and repo_id:
            repo_rec = repo_registry.get_repository(repo_id)
            if repo_rec:
                target_graph = repo_rec.graph_name
        if not target_graph:
            target_graph = self.client.primary_graph_name

        provider = custom_provider or self.llm
        is_heuristic = not provider.is_available

        commit_sha: str = ""
        if resolved_repo_id:
            repo_rec = repo_registry.get_repository(resolved_repo_id)
            if repo_rec:
                commit_sha = repo_rec.commit_sha or ""

        # 1. Target Resolution
        resolved_id: Optional[str] = None
        target_name: str = ""

        if module_identifier and module_identifier.strip():
            clean_ident = module_identifier.strip()
            resolved_id = resolve_module_id(self.client, clean_ident, graph_name=target_graph)
            if not resolved_id:
                # Bounded candidate lookup for structured unresolved response
                cand_res = execute_resolve_entity(
                    ResolveEntityInput(query=clean_ident, graph_name=target_graph),
                    client=self.client,
                )
                candidates_payload = [c.model_dump() for c in cand_res.candidates]
                unresolved_msg = f"Target module '{clean_ident}' cannot be resolved in graph '{target_graph}'."
                if cand_res.candidates:
                    top_names = ", ".join(c.module_name for c in cand_res.candidates[:3])
                    unresolved_msg += f" Did you mean one of: {top_names}?"
                else:
                    # Check whether graph contains any modules at all
                    try:
                        m_cnt = self.client.query(f"MATCH (m:{LABEL_MODULE}) RETURN count(m)", graph_name=target_graph)[
                            0
                        ][0]
                        if m_cnt == 0:
                            unresolved_msg += f" The graph '{target_graph}' currently has 0 parsed modules."
                    except Exception:
                        pass

                inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                return InvestigationReport(
                    investigation_id=inv_id,
                    question=question,
                    target_module_id=clean_ident,
                    target_module_name=clean_ident,
                    status="UNRESOLVED",
                    unresolved_reason=unresolved_msg,
                    summary=unresolved_msg,
                    ambiguity_candidates=candidates_payload,
                    repository_id=resolved_repo_id,
                    graph_name=target_graph,
                    commit_sha=commit_sha,
                    budget_used=0,
                    budget_remaining=self.max_tool_budget,
                    is_heuristic_fallback=is_heuristic,
                )
        else:
            # Natural language entity resolution
            res_entity = execute_resolve_entity(
                ResolveEntityInput(query=question, graph_name=target_graph),
                client=self.client,
            )
            if res_entity.confidence in ("EXACT", "HIGH") and res_entity.resolved_id:
                resolved_id = res_entity.resolved_id
                target_name = res_entity.resolved_name or resolved_id
            elif res_entity.confidence == "AMBIGUOUS":
                # Honest ambiguity handling: return early with clarification prompt
                inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                return InvestigationReport(
                    investigation_id=inv_id,
                    question=question,
                    target_module_id="",
                    target_module_name="",
                    status="AMBIGUOUS",
                    summary=res_entity.clarification_prompt
                    or "Multiple matching modules found. Please clarify target.",
                    ambiguity_candidates=[c.model_dump() for c in res_entity.candidates],
                    repository_id=resolved_repo_id,
                    graph_name=target_graph,
                    commit_sha=commit_sha,
                    budget_used=0,
                    budget_remaining=self.max_tool_budget,
                    is_heuristic_fallback=is_heuristic,
                )
            else:
                # Check for repository-wide or metadata question
                q_lower = question.lower()
                is_repo_wide = any(
                    w in q_lower
                    for w in ["central", "pagerank", "important", "source", "metadata", "provenance", "repository"]
                )
                if not is_repo_wide:
                    inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                    unresolved_msg = (
                        f"Could not resolve any target module from the question '{question}' "
                        f"in graph '{target_graph}'. Please specify a target module or ask "
                        "about repository-wide properties like PageRank or source metadata."
                    )
                    return InvestigationReport(
                        investigation_id=inv_id,
                        question=question,
                        target_module_id="",
                        target_module_name="",
                        status="UNRESOLVED",
                        unresolved_reason=unresolved_msg,
                        summary=unresolved_msg,
                        repository_id=resolved_repo_id,
                        graph_name=target_graph,
                        commit_sha=commit_sha,
                        budget_used=0,
                        budget_remaining=self.max_tool_budget,
                        is_heuristic_fallback=is_heuristic,
                    )

        if resolved_id and not target_name:
            name_res = self.client.query(
                f"MATCH (m:{LABEL_MODULE} {{id: $id}}) RETURN m.name LIMIT 1",
                params={"id": resolved_id},
                graph_name=target_graph,
            )
            target_name = name_res[0][0] if name_res else resolved_id

        investigation_id = f"inv_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Persist Investigation start in FalkorDB
        self._record_investigation_start(
            investigation_id, question, resolved_id or "repo_wide", created_at, target_graph
        )

        # 2. Discover MCP tools and schemas
        mcp_tools = await self.mcp_server.list_tools()
        tools_metadata = [
            {
                "name": t.name,
                "description": t.description,
            }
            for t in mcp_tools
            if t.name.startswith("nexusact_") and t.name != "nexusact_diagnose_graph"
        ]

        steps: List[InvestigationStep] = []
        investigation_history: List[Dict[str, Any]] = []

        impact_data: Optional[TraceImpactOutput] = None
        reviewer_data: Optional[WhoKnowsOutput] = None
        pagerank_data: Optional[PageRankOutput] = None
        simulation_data: Optional[SimulationResult] = None
        neighborhood_data: Optional[GraphNeighborhoodOutput] = None
        shortest_path_data: Optional[ShortestPathOutput] = None
        source_metadata_data: Optional[SourceMetadataOutput] = None
        action_proposal: Optional[Dict[str, Any]] = None
        final_summary: str = ""

        remaining_budget = self.max_tool_budget

        # 3. Adaptive Decision Loop
        while remaining_budget > 0:
            if not provider.is_available:
                decision = self._heuristic_fallback_decision(
                    question=question,
                    target_id=resolved_id,
                    steps=steps,
                    impact_data=impact_data,
                    repo_id=resolved_repo_id,
                )
            else:
                decision = await provider.decide_next_step(
                    question=question,
                    target_module_id=resolved_id or "repo_wide",
                    available_tools=tools_metadata,
                    investigation_history=investigation_history,
                    remaining_budget=remaining_budget,
                )

            if decision.action == "finish" or not decision.tool_call:
                final_summary = decision.finish_summary or "Investigation completed."
                if decision.suggested_action_title:
                    action_proposal = {
                        "title": decision.suggested_action_title,
                        "body": decision.suggested_action_body or "",
                    }
                break

            tool_call = decision.tool_call
            tool_name = tool_call.tool_name
            tool_args = tool_call.arguments or {}
            purpose = tool_call.reasoning

            # Ensure tool arguments target the module if required
            if resolved_id:
                if "module_identifier" in tool_args and not tool_args["module_identifier"]:
                    tool_args["module_identifier"] = resolved_id
                elif "module_identifier" not in tool_args and tool_name in (
                    "nexusact_trace_impact",
                    "nexusact_who_knows",
                    "nexusact_simulate_remove_module",
                    "nexusact_graph_neighborhood",
                ):
                    tool_args["module_identifier"] = resolved_id

            if "graph_name" not in tool_args and target_graph:
                tool_args["graph_name"] = target_graph

            if tool_name == "nexusact_source_metadata" and "repository_id" not in tool_args and resolved_repo_id:
                tool_args["repository_id"] = resolved_repo_id

            # 4. Invoke MCP Tool
            step_start = time.perf_counter()
            step_status = "COMPLETED"
            summary_snippet = ""

            try:
                mcp_res = await self.mcp_server.call_tool(tool_name, tool_args)
                raw_json = "{}"
                if hasattr(mcp_res, "content") and getattr(mcp_res, "content"):
                    first_item = getattr(mcp_res, "content")[0]
                    if hasattr(first_item, "text"):
                        raw_json = getattr(first_item, "text")
                parsed_res = json.loads(raw_json)

                # Process specific tool outputs
                if tool_name == "nexusact_trace_impact":
                    impact_data = TraceImpactOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Found {impact_data.total_impacted_count} upstream dependent modules "
                        f"within {impact_data.max_depth} hops."
                    )
                elif tool_name == "nexusact_who_knows":
                    reviewer_data = WhoKnowsOutput.model_validate(parsed_res)
                    names = [c.name for c in reviewer_data.candidates[:3]]
                    summary_snippet = (
                        f"Identified top candidate reviewers: {', '.join(names) if names else 'None found'}."
                    )
                elif tool_name == "nexusact_page_rank":
                    pagerank_data = PageRankOutput.model_validate(parsed_res)
                    top_mod = pagerank_data.top_modules[0].module_name if pagerank_data.top_modules else "N/A"
                    summary_snippet = f"Calculated PageRank centrality. Most central module: {top_mod}."
                elif tool_name == "nexusact_simulate_remove_module":
                    simulation_data = SimulationResult.model_validate(parsed_res)
                    summary_snippet = (
                        f"Simulated removal in cloned graph: "
                        f"{simulation_data.disappeared_paths_count} broken paths, "
                        f"{simulation_data.surviving_paths_count} surviving paths, "
                        f"blast radius score: {simulation_data.blast_radius_score:.2f}."
                    )
                elif tool_name == "nexusact_graph_neighborhood":
                    neighborhood_data = GraphNeighborhoodOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Neighborhood inspection: {len(neighborhood_data.incoming_dependents)} incoming dependents, "
                        f"{len(neighborhood_data.outgoing_dependencies)} outgoing dependencies."
                    )
                elif tool_name == "nexusact_shortest_path":
                    shortest_path_data = ShortestPathOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Shortest path from {shortest_path_data.source_id} to {shortest_path_data.target_id}: "
                        f"connected={shortest_path_data.connected}, hops={shortest_path_data.hops}."
                    )
                elif tool_name == "nexusact_source_metadata":
                    source_metadata_data = SourceMetadataOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Source metadata: {len(source_metadata_data.sources)} source adapters, "
                        f"{len(source_metadata_data.known_gaps)} known gaps disclosed."
                    )
                elif tool_name == "nexusact_resolve_entity":
                    res_out = EntityResolutionOutput.model_validate(parsed_res)
                    summary_snippet = f"Entity resolution: {res_out.confidence} match for '{res_out.query}'."

            except Exception as e:
                step_status = "FAILED"
                summary_snippet = f"Tool execution failed: {str(e)}"
                logger.error("Error executing MCP tool %s: %s", tool_name, e)

            step_duration_ms = round((time.perf_counter() - step_start) * 1000, 2)
            step_record = InvestigationStep(
                step_number=len(steps) + 1,
                tool_name=tool_name,
                arguments=tool_args,
                purpose=purpose,
                status=step_status,
                result_summary=summary_snippet,
                execution_time_ms=step_duration_ms,
            )
            steps.append(step_record)

            investigation_history.append(
                {
                    "step": step_record.step_number,
                    "tool": tool_name,
                    "purpose": purpose,
                    "status": step_status,
                    "summary": summary_snippet,
                }
            )

            # Record step in FalkorDB
            self._record_tool_step(investigation_id, step_record, target_graph)

            remaining_budget -= 1

        # 5. Run Aggregate Verification across all findings
        verification_result = self.verifier.verify_investigation(
            target_module_id=resolved_id or "repo_wide",
            impact_output=impact_data,
            reviewer_output=reviewer_data,
            simulation_output=simulation_data,
            steps=steps,
            graph_name=target_graph,
        )

        # 6. Build Proposal if requested and none generated
        if not action_proposal and ("issue" in question.lower() or "action" in question.lower()):
            action_proposal = self._generate_verified_action_proposal(
                target_name=target_name or "Repository",
                target_id=resolved_id or "repo_wide",
                impact=impact_data,
                reviewers=reviewer_data,
                simulation=simulation_data,
                verification=verification_result,
            )

        if not final_summary:
            final_summary = self._synthesize_evidence_summary(
                target_name=target_name or "Repository",
                impact=impact_data,
                reviewers=reviewer_data,
                simulation=simulation_data,
                verification=verification_result,
            )

        # Update Investigation record in FalkorDB
        self._record_investigation_finish(
            investigation_id,
            final_summary,
            verification_result.status.value if verification_result else "UNVERIFIED",
            target_graph,
        )

        return InvestigationReport(
            investigation_id=investigation_id,
            question=question,
            target_module_id=resolved_id or "",
            target_module_name=target_name or "Repository-wide",
            status="COMPLETED",
            steps=steps,
            verification=verification_result,
            summary=final_summary,
            impact_result=impact_data,
            reviewer_result=reviewer_data,
            pagerank_result=pagerank_data,
            simulation_result=simulation_data,
            neighborhood_result=neighborhood_data,
            shortest_path_result=shortest_path_data,
            source_metadata_result=source_metadata_data,
            action_proposal=action_proposal,
            repository_id=resolved_repo_id,
            graph_name=target_graph,
            commit_sha=commit_sha,
            is_heuristic_fallback=is_heuristic,
            budget_used=len(steps),
            budget_remaining=remaining_budget,
        )

    def _heuristic_fallback_decision(
        self,
        question: str,
        target_id: Optional[str],
        steps: List[InvestigationStep],
        impact_data: Optional[TraceImpactOutput],
        repo_id: Optional[str] = None,
    ) -> LLMDecision:
        """Determines the next logical tool in an evidence chain when no LLM is available."""
        called_tools = {s.tool_name for s in steps}
        q_lower = question.lower()

        # If repo-wide / no target ID
        if not target_id:
            if (
                "source" in q_lower or "metadata" in q_lower or "provenance" in q_lower or "gap" in q_lower
            ) and "nexusact_source_metadata" not in called_tools:
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_source_metadata",
                        arguments={"repository_id": repo_id or "repo:local_nexusact"},
                        reasoning="Inspect source capabilities and provenance records for repository.",
                    ),
                )
            if (
                "pagerank" in q_lower or "central" in q_lower or "important" in q_lower
            ) and "nexusact_page_rank" not in called_tools:
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_page_rank",
                        arguments={"limit": 10},
                        reasoning="Evaluate architectural centrality across the dependency network.",
                    ),
                )
            return LLMDecision(action="finish", finish_summary="Repository-level analysis complete.")

        # Target-specific adaptive tool choices
        if (
            "neighbor" in q_lower or "adjacent" in q_lower or "1-hop" in q_lower
        ) and "nexusact_graph_neighborhood" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_graph_neighborhood",
                    arguments={"module_identifier": target_id, "limit": 20},
                    reasoning="Inspect immediate 1-hop incoming and outgoing dependency connections.",
                ),
            )

        if (
            "who" in q_lower or "author" in q_lower or "review" in q_lower or "contributor" in q_lower
        ) and "nexusact_who_knows" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_who_knows",
                    arguments={"module_identifier": target_id, "limit": 5},
                    reasoning="Identify experienced contributors for this module.",
                ),
            )

        if (
            "remove" in q_lower or "simulate" in q_lower or "blast radius" in q_lower
        ) and "nexusact_simulate_remove_module" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_simulate_remove_module",
                    arguments={"module_identifier": target_id},
                    reasoning="Simulate removal in an isolated graph clone to observe topological blast radius.",
                ),
            )

        if (
            "source" in q_lower or "metadata" in q_lower or "gap" in q_lower
        ) and "nexusact_source_metadata" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_source_metadata",
                    arguments={"repository_id": repo_id or "repo:local_nexusact"},
                    reasoning="Inspect source capabilities and provenance records for repository.",
                ),
            )

        # Standard evidence chain:
        # Step 1: Trace reverse impact
        if "nexusact_trace_impact" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_trace_impact",
                    arguments={"module_identifier": target_id, "max_depth": 4},
                    reasoning="Identify upstream dependent modules that rely directly or indirectly on this target.",
                ),
            )

        # Step 2: Reviewers
        if "nexusact_who_knows" not in called_tools:
            affected = [m.module_id for m in impact_data.impacted_modules[:5]] if impact_data else []
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_who_knows",
                    arguments={"module_identifier": target_id, "affected_modules": affected, "limit": 5},
                    reasoning="Identify experienced contributors and code owners for affected components.",
                ),
            )

        # Step 3: Simulation if impact found
        if "nexusact_simulate_remove_module" not in called_tools and impact_data:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_simulate_remove_module",
                    arguments={"module_identifier": target_id},
                    reasoning="Simulate removal in an isolated graph clone to observe topological blast radius.",
                ),
            )

        # Step 4: PageRank
        if "nexusact_page_rank" not in called_tools and (
            "pagerank" in q_lower or "central" in q_lower or "important" in q_lower
        ):
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_page_rank",
                    arguments={"limit": 10},
                    reasoning="Evaluate architectural centrality across the dependency network.",
                ),
            )

        return LLMDecision(
            action="finish",
            finish_summary="Evidence-backed graph investigation concluded.",
        )

    def _generate_verified_action_proposal(
        self,
        target_name: str,
        target_id: str,
        impact: Optional[TraceImpactOutput],
        reviewers: Optional[WhoKnowsOutput],
        simulation: Optional[SimulationResult],
        verification: Optional[PathVerificationResult],
    ) -> Dict[str, Any]:
        """Constructs an action proposal strictly derived from verified graph findings."""
        title = f"[NexusAct] Architecture impact report for {target_name}"

        body_lines = [
            f"## NexusAct Investigation Summary for `{target_name}`",
            "",
            f"**Target Module ID:** `{target_id}`",
            f"**Graph Verification Status:** `{verification.status.value if verification else 'UNVERIFIED'}`",
            "",
            "### Upstream Impact Analysis",
        ]

        if impact and impact.impacted_modules:
            body_lines.append(f"- **Total Affected Modules:** {impact.total_impacted_count}")
            body_lines.append(f"- **Max Traversal Depth:** {impact.max_depth} hops")
            body_lines.append("- **Direct/Indirect Callers:**")
            for m in impact.impacted_modules[:5]:
                body_lines.append(f"  - `{m.module_name}` ({m.hops} hop{'s' if m.hops > 1 else ''})")
            if impact.is_truncated:
                body_lines.append("  - *(Additional callers truncated at query limit)*")
        else:
            body_lines.append("- *No upstream modules directly or indirectly depend on this module.*")

        if simulation:
            body_lines.extend(
                [
                    "",
                    "### Counterfactual Simulation (Isolated Cloned Graph)",
                    (
                        "- **Disrupted Dependency Paths:** "
                        f"{simulation.disappeared_paths_count} / {simulation.baseline_paths_count}"
                    ),
                    f"- **Surviving Paths:** {simulation.surviving_paths_count}",
                    f"- **Blast Radius Score:** {simulation.blast_radius_score:.3f} (broken/baseline paths)",
                    f"- **Surviving Modules in Copy:** {simulation.surviving_modules_count}",
                    f"> Note: {simulation.disclaimer}",
                ]
            )

        if reviewers and reviewers.candidates:
            body_lines.extend(
                [
                    "",
                    "### Recommended Reviewers (Evidence-Derived)",
                ]
            )
            for c in reviewers.candidates[:3]:
                body_lines.append(f"- **{c.name}** (Score: {c.composite_score:.2f}) — {c.rationale}")

        body_lines.extend(
            [
                "",
                "---",
                "*Report generated deterministically by NexusAct GraphAction Fabric.*",
            ]
        )

        return {
            "title": title,
            "body": "\n".join(body_lines),
        }

    def _synthesize_evidence_summary(
        self,
        target_name: str,
        impact: Optional[TraceImpactOutput],
        reviewers: Optional[WhoKnowsOutput],
        simulation: Optional[SimulationResult],
        verification: Optional[PathVerificationResult],
    ) -> str:
        """Synthesizes a human-readable summary of the evidence collected."""
        parts = [f"Investigation of module '{target_name}':"]
        if impact:
            parts.append(f"Identified {impact.total_impacted_count} upstream dependent modules within 4 hops.")
        if simulation:
            parts.append(
                f"Simulated module removal indicated {simulation.disappeared_paths_count} broken dependency paths "
                f"with a blast radius of {simulation.blast_radius_score:.2f}."
            )
        if reviewers and reviewers.candidates:
            names = ", ".join([c.name for c in reviewers.candidates[:2]])
            parts.append(f"Primary suggested reviewers with relevant commit history: {names}.")
        if verification:
            parts.append(f"Graph topology verification status: {verification.status.value}.")

        return " ".join(parts)

    def _record_investigation_start(
        self, inv_id: str, question: str, target_id: str, created_at: str, graph_name: str
    ) -> None:
        try:
            self.client.query(
                """
                MERGE (inv:Investigation {id: $id})
                SET inv.question = $q,
                    inv.target_module_id = $target,
                    inv.status = 'IN_PROGRESS',
                    inv.created_at = $created_at
                """,
                params={"id": inv_id, "q": question, "target": target_id, "created_at": created_at},
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to record investigation start in FalkorDB: %s", e)

    def _record_tool_step(self, inv_id: str, step: InvestigationStep, graph_name: str) -> None:
        try:
            step_id = f"step_{inv_id}_{step.step_number}"
            now_iso = datetime.now(timezone.utc).isoformat()
            self.client.query(
                """
                MATCH (inv:Investigation {id: $inv_id})
                MERGE (t:ToolInvocation {id: $step_id})
                SET t.tool_name = $tool_name,
                    t.purpose = $purpose,
                    t.status = $status,
                    t.result_summary = $summary,
                    t.execution_time_ms = $duration,
                    t.timestamp = $ts
                MERGE (inv)-[:USED_TOOL]->(t)
                """,
                params={
                    "inv_id": inv_id,
                    "step_id": step_id,
                    "tool_name": step.tool_name,
                    "purpose": step.purpose,
                    "status": step.status,
                    "summary": step.result_summary,
                    "duration": step.execution_time_ms,
                    "ts": now_iso,
                },
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to record tool step in FalkorDB: %s", e)

    def _record_investigation_finish(
        self, inv_id: str, summary: str, verification_status: str, graph_name: str
    ) -> None:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.client.query(
                """
                MATCH (inv:Investigation {id: $inv_id})
                SET inv.status = 'COMPLETED',
                    inv.summary = $summary,
                    inv.verification_status = $v_status,
                    inv.finished_at = $ts
                """,
                params={
                    "inv_id": inv_id,
                    "summary": summary,
                    "v_status": verification_status,
                    "ts": now_iso,
                },
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to record investigation finish in FalkorDB: %s", e)
