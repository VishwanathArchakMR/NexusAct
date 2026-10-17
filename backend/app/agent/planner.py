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
from backend.app.graph.tools.fraud import FraudInvestigationOutput
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
from backend.app.graph.tools.security_triage import SecurityTriageOutput
from backend.app.graph.tools.shortest_path import ShortestPathOutput
from backend.app.graph.tools.simulation import SimulationResult
from backend.app.sources.freshness import source_freshness_service
from backend.app.sources.models import SourceMetadataOutput, SourceSnapshot
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
    investigation_mode: str = "codebase_walkthrough"
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
    security_triage_result: Optional[SecurityTriageOutput] = None
    fraud_result: Optional[FraudInvestigationOutput] = None
    source_snapshot: Optional[SourceSnapshot] = None
    snapshot_id: Optional[str] = None
    freshness_status: str = "FRESH"
    working_tree_fingerprint: Optional[str] = None
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
        investigation_mode: Optional[str] = None,
    ) -> InvestigationReport:
        """Executes adaptive investigation with source freshness and multi-repo isolation."""
        target_graph = graph_name
        resolved_repo_id = repo_id
        commit_sha: str = ""
        source_snapshot: Optional[SourceSnapshot] = None
        working_tree_fp: Optional[str] = None
        freshness_status: str = "FRESH"
        snapshot_id: Optional[str] = None

        provider = custom_provider or self.llm
        is_heuristic = not provider.is_available

        q_lower = question.lower()
        if investigation_mode:
            mode = investigation_mode.lower()
        elif any(
            w in q_lower
            for w in [
                "security",
                "vulnerability",
                "cve",
                "triage",
                "compromise",
                "advisory",
                "audit",
                "finding",
            ]
        ):
            mode = "security_triage"
        elif any(
            w in q_lower
            for w in [
                "fraud",
                "suspicious",
                "transfer",
                "cycle",
                "laundering",
                "ring",
            ]
        ):
            mode = "fraud_demo"
        elif any(
            w in q_lower
            for w in [
                "break",
                "impact",
                "simulate",
                "remove",
                "blast radius",
                "refactor",
            ]
        ):
            mode = "change_impact"
        else:
            mode = "codebase_walkthrough"

        if mode == "fraud_demo":
            target_graph = "nexusact_fraud_demo"
            resolved_repo_id = "synthetic_fraud_demo"
            commit_sha = "SYNTHETIC_DATA_V1"
            from backend.app.sources.models import SourceType

            source_snapshot = SourceSnapshot(
                snapshot_id="snap_fraud_demo",
                repository_id="synthetic_fraud_demo",
                source_type=SourceType.LOCAL,
                canonical_source="nexusact_fraud_demo",
                commit_sha="SYNTHETIC",
                graph_name="nexusact_fraud_demo",
                freshness_status="FRESH",
            )
            snapshot_id = "snap_fraud_demo"
        elif repo_id:
            repo_rec = repo_registry.get_repository(repo_id)
            if not repo_rec and not graph_name:
                # Specified repo_id does not exist in registry; return UNRESOLVED without cross-graph leakage
                inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                return InvestigationReport(
                    investigation_id=inv_id,
                    question=question,
                    target_module_id=module_identifier or "",
                    target_module_name=module_identifier or "Unknown",
                    status="UNRESOLVED",
                    investigation_mode=mode,
                    summary=(
                        f"Repository '{repo_id}' is not registered. "
                        "Cannot execute investigation across an unvalidated graph context."
                    ),
                    unresolved_reason=(
                        f"Repository '{repo_id}' is not registered in repository registry. "
                        "Cross-graph execution refused."
                    ),
                    repository_id=repo_id,
                    graph_name="",
                    commit_sha="",
                    is_heuristic_fallback=is_heuristic,
                    steps=[],
                    budget_used=0,
                    budget_remaining=self.max_tool_budget,
                )
            elif repo_rec:
                try:
                    source_snapshot = source_freshness_service.check_and_refresh_source(repo_id)
                    target_graph = source_snapshot.graph_name
                    commit_sha = source_snapshot.commit_sha
                    working_tree_fp = source_snapshot.working_tree_fingerprint
                    snapshot_id = source_snapshot.snapshot_id
                    freshness_status = source_snapshot.freshness_status
                except Exception as _fe:
                    logger.warning("Freshness check error on %s: %s", repo_id, _fe)
                    target_graph = repo_rec.graph_name
                    commit_sha = repo_rec.commit_sha or ""
                    freshness_status = "STALE_SOURCE_UNAVAILABLE"
                    source_snapshot = repo_rec.to_snapshot()
        elif graph_name:
            target_graph = graph_name
            rec = repo_registry.get_repository(graph_name)
            if rec:
                resolved_repo_id = rec.id
                commit_sha = rec.commit_sha
                snapshot_id = rec.active_snapshot_id
                source_snapshot = rec.to_snapshot()
        else:
            # Default to local workspace
            local_rec = repo_registry.get_repository("repo:local_nexusact")
            if local_rec:
                resolved_repo_id = local_rec.id
                try:
                    source_snapshot = source_freshness_service.check_and_refresh_source("repo:local_nexusact")
                    target_graph = source_snapshot.graph_name
                    commit_sha = source_snapshot.commit_sha
                    working_tree_fp = source_snapshot.working_tree_fingerprint
                    snapshot_id = source_snapshot.snapshot_id
                    freshness_status = source_snapshot.freshness_status
                except Exception as _lfe:
                    logger.warning("Local freshness check error: %s", _lfe)
                    target_graph = local_rec.graph_name
                    commit_sha = local_rec.commit_sha or ""
                    source_snapshot = local_rec.to_snapshot()
            else:
                target_graph = target_graph or self.client.primary_graph_name

        if not target_graph:
            target_graph = self.client.primary_graph_name

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
                    investigation_mode=mode,
                    unresolved_reason=unresolved_msg,
                    summary=unresolved_msg,
                    ambiguity_candidates=candidates_payload,
                    repository_id=resolved_repo_id,
                    graph_name=target_graph,
                    commit_sha=commit_sha,
                    source_snapshot=source_snapshot,
                    snapshot_id=snapshot_id,
                    freshness_status=freshness_status,
                    working_tree_fingerprint=working_tree_fp,
                    budget_used=0,
                    budget_remaining=self.max_tool_budget,
                    is_heuristic_fallback=is_heuristic,
                )
        else:
            q_lower = question.lower()
            is_path_query = any(w in q_lower for w in ["path", "trace", "flow", "connect", "between", "how does"])
            if mode in ("security_triage", "fraud_demo"):
                resolved_id = None
                target_name = "Repository-wide"
            elif is_path_query and (
                "api" in q_lower and ("graph" in q_lower or "storage" in q_lower or "database" in q_lower)
            ):
                resolved_id = "mod:backend.app.api.router"
                target_name = "backend.app.api.router -> backend.app.graph.client"
            else:
                # Natural language entity resolution
                res_entity = execute_resolve_entity(
                    ResolveEntityInput(query=question, graph_name=target_graph),
                    client=self.client,
                )
                if res_entity.confidence in ("EXACT", "HIGH") and res_entity.resolved_id:
                    resolved_id = res_entity.resolved_id
                    target_name = res_entity.resolved_name or resolved_id
                elif is_path_query and res_entity.confidence == "AMBIGUOUS" and len(res_entity.candidates) >= 2:
                    # Multi-node path traversal: select source candidate
                    resolved_id = res_entity.candidates[0].module_id
                    target_name = res_entity.candidates[0].module_name
                elif res_entity.confidence == "AMBIGUOUS":
                    # Honest ambiguity handling: return early with clarification prompt
                    inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                    return InvestigationReport(
                        investigation_id=inv_id,
                        question=question,
                        target_module_id="",
                        target_module_name="",
                        status="AMBIGUOUS",
                        investigation_mode=mode,
                        summary=res_entity.clarification_prompt
                        or "Multiple matching modules found. Please clarify target.",
                        ambiguity_candidates=[c.model_dump() for c in res_entity.candidates],
                        repository_id=resolved_repo_id,
                        graph_name=target_graph,
                        commit_sha=commit_sha,
                        source_snapshot=source_snapshot,
                        snapshot_id=snapshot_id,
                        freshness_status=freshness_status,
                        working_tree_fingerprint=working_tree_fp,
                        budget_used=0,
                        budget_remaining=self.max_tool_budget,
                        is_heuristic_fallback=is_heuristic,
                    )
                else:
                    # Check for repository-wide, security, path, or domain (e.g. fraud) question
                    is_repo_wide = is_path_query or any(
                        w in q_lower
                        for w in [
                            "central",
                            "pagerank",
                            "important",
                            "source",
                            "metadata",
                            "provenance",
                            "repository",
                            "fraud",
                            "transfer",
                            "suspicious",
                            "transaction",
                            "vulnerability",
                            "security",
                            "triage",
                            "cve",
                            "osv",
                            "dependency",
                            "path",
                            "trace",
                            "flow",
                        ]
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
                            investigation_mode=mode,
                            unresolved_reason=unresolved_msg,
                            summary=unresolved_msg,
                            repository_id=resolved_repo_id,
                            graph_name=target_graph,
                            commit_sha=commit_sha,
                            source_snapshot=source_snapshot,
                            snapshot_id=snapshot_id,
                            freshness_status=freshness_status,
                            working_tree_fingerprint=working_tree_fp,
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
        security_triage_data: Optional[SecurityTriageOutput] = None
        fraud_data: Optional[FraudInvestigationOutput] = None
        action_proposal: Optional[Dict[str, Any]] = None
        final_summary: str = ""

        remaining_budget = self.max_tool_budget

        # 3. Adaptive Decision Loop
        executed_calls = set()
        while remaining_budget > 0:
            if not provider.is_available:
                decision = self._heuristic_fallback_decision(
                    question=question,
                    target_id=resolved_id,
                    steps=steps,
                    impact_data=impact_data,
                    repo_id=resolved_repo_id,
                    investigation_mode=mode,
                    security_triage_data=security_triage_data,
                    fraud_data=fraud_data,
                )
            else:
                decision = await provider.decide_next_step(
                    question=question,
                    target_module_id=resolved_id or "repo_wide",
                    available_tools=tools_metadata,
                    investigation_history=investigation_history,
                    remaining_budget=remaining_budget,
                    investigation_mode=mode,
                    graph_context=target_graph,
                    source_revision=commit_sha,
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

            # Strict tool allowlist enforcement
            valid_tool_names = {t["name"] for t in tools_metadata}
            if tool_name not in valid_tool_names:
                logger.warning("Model requested unapproved or unknown tool: '%s'. Rejecting step.", tool_name)
                remaining_budget -= 1
                continue

            # Ensure tool arguments target the resolved module if required
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

            # Strictly enforce graph context: model cannot override selected graph
            if tool_name == "nexusact_investigate_fraud":
                tool_args["graph_name"] = "nexusact_fraud_demo"
            elif target_graph:
                tool_args["graph_name"] = target_graph

            if tool_name == "nexusact_source_metadata" and "repository_id" not in tool_args and resolved_repo_id:
                tool_args["repository_id"] = resolved_repo_id

            if tool_name == "nexusact_security_triage" and "repository_id" not in tool_args and resolved_repo_id:
                tool_args["repository_id"] = resolved_repo_id

            # Loop detection: detect repeated calls with equivalent arguments and stop pointless loops
            call_sig = (tool_name, json.dumps(tool_args, sort_keys=True))
            if call_sig in executed_calls:
                logger.info(
                    "Planner detected repeated tool call '%s' with equivalent arguments. Ending loop.",
                    tool_name,
                )
                final_summary = (
                    decision.finish_summary
                    or f"Investigation concluded: sufficient evidence collected; stopped loop on '{tool_name}'."
                )
                break
            executed_calls.add(call_sig)

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
                elif tool_name == "nexusact_security_triage":
                    security_triage_data = SecurityTriageOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Security triage: {security_triage_data.total_vulnerabilities_count} vulnerabilities "
                        f"across {security_triage_data.dependencies_analyzed_count} dependencies."
                    )
                elif tool_name == "nexusact_investigate_fraud":
                    fraud_data = FraudInvestigationOutput.model_validate(parsed_res)
                    summary_snippet = (
                        f"Synthetic fraud demo: {len(fraud_data.patterns_detected)} patterns detected, "
                        f"risk indicator={fraud_data.risk_indicator}."
                    )

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

        # 6. Build Proposal tailored to investigation
        if not action_proposal:
            action_proposal = self._generate_verified_action_proposal(
                target_name=target_name or "Repository",
                target_id=resolved_id or "repo_wide",
                impact=impact_data,
                reviewers=reviewer_data,
                simulation=simulation_data,
                verification=verification_result,
                question=question,
                security_triage=security_triage_data,
                fraud=fraud_data,
            )

        if not final_summary:
            final_summary = self._synthesize_evidence_summary(
                target_name=target_name or "Repository",
                impact=impact_data,
                reviewers=reviewer_data,
                simulation=simulation_data,
                verification=verification_result,
                security_triage=security_triage_data,
                fraud=fraud_data,
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
            investigation_mode=mode,
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
            security_triage_result=security_triage_data,
            fraud_result=fraud_data,
            action_proposal=action_proposal,
            repository_id=resolved_repo_id,
            graph_name=target_graph,
            commit_sha=commit_sha,
            source_snapshot=source_snapshot,
            snapshot_id=snapshot_id,
            freshness_status=freshness_status,
            working_tree_fingerprint=working_tree_fp,
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
        investigation_mode: str = "codebase_walkthrough",
        security_triage_data: Optional[SecurityTriageOutput] = None,
        fraud_data: Optional[FraudInvestigationOutput] = None,
    ) -> LLMDecision:
        """Determines the next logical graph tool based on workflow mode, question intent, and collected evidence."""
        called_tools = {s.tool_name for s in steps}
        q_lower = question.lower()
        mode = (investigation_mode or "codebase_walkthrough").lower()

        # ======================================================================
        # 1. SPECIALIZED WORKFLOW: FRAUD INVESTIGATION DEMO
        # ======================================================================
        is_fraud = mode == "fraud_demo" or any(
            w in q_lower for w in ["fraud", "suspicious", "transfer", "cycle", "laundering", "ring"]
        )
        if is_fraud:
            if "nexusact_investigate_fraud" not in called_tools:
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_investigate_fraud",
                        arguments={
                            "question": question,
                            "target_account_id": target_id if target_id and target_id.startswith("acc:") else None,
                            "graph_name": "nexusact_fraud_demo",
                        },
                        reasoning=(
                            "Investigate multi-hop transfer cycles, shared device infrastructure, "
                            "and benign controls in synthetic fraud demonstration graph."
                        ),
                    ),
                )
            # Once fraud investigation is executed, finish with complete evidence summary
            return LLMDecision(
                action="finish",
                finish_summary=(
                    "Synthetic fraud pattern investigation, multi-hop cycle detection, "
                    "and benign control audit completed."
                ),
            )

        # ======================================================================
        # 2. SPECIALIZED WORKFLOW: SECURITY TRIAGE (OSV)
        # ======================================================================
        is_security = mode == "security_triage" or any(
            w in q_lower
            for w in ["security", "vulnerability", "cve", "triage", "compromise", "advisory", "audit", "osv"]
        )
        if is_security:
            if "nexusact_security_triage" not in called_tools:
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_security_triage",
                        arguments={"repository_id": repo_id or "repo:local_nexusact"},
                        reasoning=(
                            "Triage declared repository dependencies against public OSV vulnerability records "
                            "and map internal module reachability."
                        ),
                    ),
                )
            # If vulnerabilities found have affected internal modules, trace their reachability impact
            if (
                security_triage_data
                and security_triage_data.vulnerabilities_found
                and "nexusact_trace_impact" not in called_tools
            ):
                for v in security_triage_data.vulnerabilities_found:
                    if v.affected_modules:
                        aff_target = v.affected_modules[0]
                        return LLMDecision(
                            action="call_tool",
                            tool_call=LLMToolCall(
                                tool_name="nexusact_trace_impact",
                                arguments={"module_identifier": aff_target, "max_depth": 3},
                                reasoning=(
                                    f"Trace reachability blast radius for internal module '{aff_target}' "
                                    f"affected by vulnerable dependency '{v.package_name}'."
                                ),
                            ),
                        )
            return LLMDecision(
                action="finish",
                finish_summary=(
                    "Security vulnerability triage, internal module reachability, and remediation analysis completed."
                ),
            )

        # ======================================================================
        # 3. CODEBASE WALKTHROUGH & ARCHITECTURAL INVESTIGATION
        # ======================================================================
        # A. Multi-hop Path / Flow Query (e.g. "How does an API request reach the graph storage layer?")
        import re

        is_path_query = any(
            w in q_lower for w in ["path", "flow", "connect", "reach", "between", "from", "to", "route", "pipeline"]
        )

        path_match = re.search(
            r"(?:between|from)\s+([`'\"]?[\w\.\/\-]+[`'\"]?)\s+(?:and|to)\s+([`'\"]?[\w\.\/\-]+[`'\"]?)",
            question,
            re.IGNORECASE,
        )
        if not path_match:
            path_match = re.search(
                r"how does\s+([`'\"]?[\w\.\/\-]+[`'\"]?)\s+connect(?:s)?\s+to\s+([`'\"]?[\w\.\/\-]+[`'\"]?)",
                question,
                re.IGNORECASE,
            )

        if is_path_query and "nexusact_shortest_path" not in called_tools:
            if path_match:
                src_raw = path_match.group(1).strip("`'\" ")
                dst_raw = path_match.group(2).strip("`'\" ")
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_shortest_path",
                        arguments={"source_identifier": src_raw, "target_identifier": dst_raw},
                        reasoning=f"Trace topological path and multi-hop connections from {src_raw} to {dst_raw}.",
                    ),
                )
            elif "api" in q_lower and ("graph" in q_lower or "storage" in q_lower or "database" in q_lower):
                # Well-known architectural traversal: API router -> endpoints -> graph storage (multi-hop)
                src_cand = "backend.app.api.router"
                dst_cand = "backend.app.graph.client"
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_shortest_path",
                        arguments={"source_identifier": src_cand, "target_identifier": dst_cand},
                        reasoning="Trace multi-hop path from API router through endpoints to graph storage client.",
                    ),
                )
            elif target_id:
                # If path query with single target, inspect its 1-hop and 2-hop structural neighborhood
                if "nexusact_graph_neighborhood" not in called_tools:
                    return LLMDecision(
                        action="call_tool",
                        tool_call=LLMToolCall(
                            tool_name="nexusact_graph_neighborhood",
                            arguments={"module_identifier": target_id, "limit": 20},
                            reasoning="Inspect incoming callers and outgoing callees defining connection paths.",
                        ),
                    )

        if "nexusact_shortest_path" in called_tools and not any(
            w in q_lower for w in ["break", "impact", "affect", "modify", "remove", "refactor"]
        ):
            return LLMDecision(
                action="finish",
                finish_summary="Shortest path exploration and multi-hop relationship verification completed.",
            )

        # B. Centrality / PageRank Architecture Query
        if (
            any(w in q_lower for w in ["pagerank", "central", "important", "critical", "backbone", "ranking"])
            and "nexusact_page_rank" not in called_tools
        ):
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_page_rank",
                    arguments={"limit": 10},
                    reasoning=(
                        "Evaluate architectural centrality and identify critical dependency hubs across the codebase."
                    ),
                ),
            )
        if "nexusact_page_rank" in called_tools and not any(
            w in q_lower for w in ["break", "impact", "affect", "modify", "remove"]
        ):
            return LLMDecision(
                action="finish",
                finish_summary="PageRank centrality analysis and critical dependency hub evaluation complete.",
            )

        # C. Contributor / Reviewer / Code Ownership Query
        is_ownership_query = any(
            w in q_lower for w in ["who", "author", "review", "contributor", "experience", "owner", "ownership"]
        )
        if is_ownership_query and "nexusact_who_knows" not in called_tools and target_id:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_who_knows",
                    arguments={"module_identifier": target_id, "limit": 5},
                    reasoning="Identify experienced contributors, commit authors, and designated code reviewers.",
                ),
            )
        if "nexusact_who_knows" in called_tools and not any(
            w in q_lower for w in ["break", "impact", "affect", "refactor", "modify", "remove", "risk"]
        ):
            return LLMDecision(
                action="finish",
                finish_summary="Reviewer and contributor ownership evidence analysis complete.",
            )

        # D. Source Metadata / Provenance Query
        if (
            any(w in q_lower for w in ["source", "metadata", "provenance", "gap", "capabilities"])
            and "nexusact_source_metadata" not in called_tools
        ):
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_source_metadata",
                    arguments={"repository_id": repo_id or "repo:local_nexusact"},
                    reasoning="Inspect repository source capabilities, freshness records, and known modeling gaps.",
                ),
            )
        if "nexusact_source_metadata" in called_tools and not any(
            w in q_lower for w in ["break", "impact", "modify", "affect"]
        ):
            return LLMDecision(
                action="finish",
                finish_summary="Source capabilities and provenance inspection complete.",
            )

        # E. Immediate Callers / Callees / Neighborhood / Wiring Query
        if (
            any(
                w in q_lower
                for w in [
                    "neighbor",
                    "caller",
                    "callee",
                    "entry",
                    "wire",
                    "adjacent",
                    "1-hop",
                    "dependency",
                    "dependents",
                ]
            )
            and "nexusact_graph_neighborhood" not in called_tools
            and target_id
        ):
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_graph_neighborhood",
                    arguments={"module_identifier": target_id, "limit": 20},
                    reasoning="Inspect immediate 1-hop incoming callers and outgoing callee dependencies.",
                ),
            )
        if "nexusact_graph_neighborhood" in called_tools and not any(
            w in q_lower for w in ["break", "impact", "modify", "affect", "remove", "simulate"]
        ):
            return LLMDecision(
                action="finish",
                finish_summary="Immediate neighborhood caller/callee inspection complete.",
            )

        # F. Change Impact / Modification / Refactoring / Simulation Query
        is_change_query = any(
            w in q_lower
            for w in [
                "modify",
                "change",
                "affect",
                "impact",
                "break",
                "refactor",
                "remove",
                "blast radius",
                "simulation",
            ]
        )

        if is_change_query and target_id:
            # Step 1: Trace reverse impact
            if "nexusact_trace_impact" not in called_tools:
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_trace_impact",
                        arguments={"module_identifier": target_id, "max_depth": 4},
                        reasoning=(
                            "Identify upstream dependent modules that rely directly or indirectly on this target."
                        ),
                    ),
                )
            # Step 2: Simulation if question asks for removal, simulation, blast radius, or failure
            if (
                any(w in q_lower for w in ["remove", "simulate", "blast radius", "counterfactual", "break", "fail"])
                and "nexusact_simulate_remove_module" not in called_tools
            ):
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_simulate_remove_module",
                        arguments={"module_identifier": target_id},
                        reasoning="Simulate removal in an isolated graph clone to observe topological path disruption.",
                    ),
                )
            # Step 3: Who to alert if requested
            if (
                any(w in q_lower for w in ["who", "alert", "review", "owner"])
                and "nexusact_who_knows" not in called_tools
            ):
                affected = [m.module_id for m in impact_data.impacted_modules[:5]] if impact_data else []
                return LLMDecision(
                    action="call_tool",
                    tool_call=LLMToolCall(
                        tool_name="nexusact_who_knows",
                        arguments={"module_identifier": target_id, "affected_modules": affected, "limit": 5},
                        reasoning="Identify experienced code owners for impacted components.",
                    ),
                )
            return LLMDecision(
                action="finish",
                finish_summary="Change impact and dependency blast radius investigation completed.",
            )

        # G. General explanation of target module (e.g. "Explain module X" or "What does module X do?")
        if target_id and "nexusact_graph_neighborhood" not in called_tools:
            return LLMDecision(
                action="call_tool",
                tool_call=LLMToolCall(
                    tool_name="nexusact_graph_neighborhood",
                    arguments={"module_identifier": target_id, "limit": 20},
                    reasoning=(
                        f"Inspect callers and callees for target module '{target_id}' to explain its structural role."
                    ),
                ),
            )

        # Repository-level default finish
        return LLMDecision(
            action="finish",
            finish_summary="Investigation concluded based on available graph evidence.",
        )

    def _generate_verified_action_proposal(
        self,
        target_name: str,
        target_id: str,
        impact: Optional[TraceImpactOutput],
        reviewers: Optional[WhoKnowsOutput],
        simulation: Optional[SimulationResult],
        verification: Optional[PathVerificationResult],
        question: str = "",
        security_triage: Optional[SecurityTriageOutput] = None,
        fraud: Optional[FraudInvestigationOutput] = None,
    ) -> Dict[str, Any]:
        """Constructs an action proposal strictly derived from verified graph findings."""
        if security_triage:
            title = (
                f"[NexusAct Security Triage] Remediate {security_triage.total_vulnerabilities_count} "
                f"public vulnerabilities in {security_triage.repository_id}"
            )
            body_lines = [
                f"## NexusAct Security Triage Report ({security_triage.repository_id})",
                "",
                f"**Graph Context:** `{security_triage.graph_name}`",
                f"**Manifests Inspected:** {', '.join(security_triage.manifests_inspected) or 'Standard manifests'}",
                f"**Dependencies Scanned:** {security_triage.dependencies_analyzed_count}",
                (
                    f"**Advisories Identified:** {security_triage.total_vulnerabilities_count} "
                    f"(Critical: {security_triage.critical_count}, High: {security_triage.high_count})"
                ),
                "",
                "### Remediation Action Plan",
                security_triage.remediation_proposal,
                "",
                "### Public Vulnerability Evidence (OSV-Backed)",
            ]
            for v in security_triage.vulnerabilities_found[:5]:
                fix_str = v.fixed_version or "N/A"
                pkg_info = f"`{v.package_name}@{v.package_version}`"
                body_lines.append(f"- **{v.vuln_id}** ({pkg_info}, Severity: {v.severity}) — Fixed in: `{fix_str}`")
                body_lines.append(f"  - Advisory Source: {v.source_url}")
                if v.affected_modules:
                    body_lines.append(f"  - Consumed by internal modules: {', '.join(v.affected_modules)}")
            body_lines.extend(
                [
                    "",
                    "---",
                    "*Action proposal generated from public OSV vulnerability records in FalkorDB.*",
                ]
            )
            return {"title": title, "body": "\n".join(body_lines)}

        if fraud:
            title = f"[NexusAct Fraud Review] Synthetic Multi-Hop Transfer Audit ({fraud.graph_name})"
            body_lines = [
                "## NexusAct Synthetic Fraud Demonstration Review",
                f"> **Synthetic Disclaimer:** {fraud.synthetic_disclaimer}",
                "",
                f"**Graph Context:** `{fraud.graph_name}`",
                f"**Risk Indicator:** `{fraud.risk_indicator}`",
                f"**Suspicious Flow Volume:** ${fraud.total_suspicious_volume_usd:,.2f}",
                "",
                "### Detected Topology Patterns",
            ]
            for p in fraud.patterns_detected:
                body_lines.append(f"- **{p.pattern_type}** ({p.severity}): {p.description}")
                body_lines.append(f"  - Criteria: {p.evidence_criteria}")
                if p.multi_hop_path:
                    body_lines.append(f"  - Multi-Hop Chain: {' -> '.join(p.multi_hop_path)}")
            body_lines.extend(
                [
                    "",
                    "### Benign Control Verification",
                ]
            )
            for ctrl in fraud.benign_controls:
                body_lines.append(f"- **{ctrl.account_id}**: {ctrl.reason}")
            body_lines.extend(
                [
                    "",
                    "### Recommended Case Action",
                    fraud.recommended_action,
                    "",
                    "---",
                    "*Action proposal recorded in FalkorDB for demonstration case review.*",
                ]
            )
            return {"title": title, "body": "\n".join(body_lines)}

        q_lower = question.lower()
        if any(w in q_lower for w in ["who", "author", "review", "contributor", "experience"]) and not any(
            w in q_lower for w in ["break", "impact", "refactor", "risk"]
        ):
            title = f"[NexusAct Code Ownership] Designate experienced code reviewers for {target_name}"
        elif any(w in q_lower for w in ["path", "connect", "between"]):
            title = f"[NexusAct Path Verification] Multi-hop relationship path analysis for {target_name}"
        else:
            title = f"[NexusAct Impact Analysis] Safe refactoring guardrails for {target_name}"

        body_lines = [
            f"## NexusAct Investigation Summary for `{target_name}`",
            "",
            f"**Target Module ID:** `{target_id}`",
            f"**Graph Verification Status:** `{verification.status.value if verification else 'UNVERIFIED'}`",
            f"**Original Investigation Question:** {question or 'N/A'}",
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
            body_lines.append(
                "- *No modeled upstream dependency path was found in this snapshot. "
                "The result is limited by the current parser and relationship coverage.*"
            )

        if simulation:
            blast_display = (
                f"{simulation.blast_radius_score:.3f} (broken/baseline paths)"
                if simulation.baseline_paths_count > 0
                else "N/A (no affected baseline dependency paths)"
            )
            body_lines.extend(
                [
                    "",
                    "### Counterfactual Simulation (Isolated Cloned Graph)",
                    (
                        "- **Disrupted Dependency Paths:** "
                        f"{simulation.disappeared_paths_count} / {simulation.baseline_paths_count}"
                    ),
                    f"- **Surviving Paths:** {simulation.surviving_paths_count}",
                    f"- **Blast Radius Score:** {blast_display}",
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
            if reviewers.evidence_status == "NO_REVIEW_DATA":
                body_lines.append(
                    "> **Reviewer Evidence Notice:** PR peer review records unavailable in local Git history "
                    "(status: `NO_REVIEW_DATA`). Scoring reflects historical commit changes and file modifications."
                )
            for cand in reviewers.candidates[:3]:
                body_lines.append(f"- **{cand.name}** (Score: {cand.composite_score:.2f}) — {cand.rationale}")

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
        security_triage: Optional[SecurityTriageOutput] = None,
        fraud: Optional[FraudInvestigationOutput] = None,
    ) -> str:
        """Synthesizes a human-readable summary of the evidence collected."""
        parts = []
        if security_triage:
            parts.append(
                f"Security triage inspected dependencies in '{security_triage.repository_id}' and found "
                f"{security_triage.total_vulnerabilities_count} public vulnerability advisories "
                f"across {security_triage.dependencies_analyzed_count} packages."
            )
        if fraud:
            parts.append(
                f"Synthetic fraud traversal in '{fraud.graph_name}' detected {len(fraud.patterns_detected)} "
                f"suspicious pattern(s) with ${fraud.total_suspicious_volume_usd:,.2f} total flow, "
                f"while confirming benign controls."
            )
        if not security_triage and not fraud:
            parts.append(f"Investigation of module '{target_name}':")
            if impact:
                if impact.total_impacted_count > 0:
                    parts.append(f"Identified {impact.total_impacted_count} upstream dependent modules within 4 hops.")
                else:
                    parts.append(
                        "No modeled upstream dependency path was found in this snapshot. "
                        "The result is limited by the current parser and relationship coverage."
                    )
            if simulation:
                if simulation.baseline_paths_count > 0:
                    parts.append(
                        f"Simulated module removal indicated {simulation.disappeared_paths_count} broken paths "
                        f"with a blast radius of {simulation.blast_radius_score:.2f}."
                    )
                else:
                    parts.append(
                        "Simulated module removal indicated 0 affected baseline dependency paths (blast radius N/A)."
                    )
            if reviewers and reviewers.candidates:
                names = ", ".join([c.name for c in reviewers.candidates[:2]])
                if reviewers.evidence_status == "NO_REVIEW_DATA":
                    parts.append(f"Contributors with relevant commit history: {names} (PR reviews unavailable).")
                else:
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
