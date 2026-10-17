"""Graph-Grounded AI Chat Assistant Service for NexusAct.

Enables source-aware natural language conversation grounded in FalkorDB graph reasoning,
schema discovery, verified read-only Cypher execution, and explicit evidence citations.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.agent.llm import GeminiProvider, get_llm_provider
from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.sources.registry import repo_registry

logger = logging.getLogger("nexusact.agent.chat")

# Disallowed Cypher keywords that mutate graph state or invoke administrative commands
_FORBIDDEN_MUTATION_PATTERNS = [
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bSET\b",
    r"\bDELETE\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bDETACH\s+DELETE\b",
    r"\bCALL\s+db\.create",
    r"\bCALL\s+db\.drop",
    r"\bCALL\s+dbms\.",
]


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    timestamp: Optional[str] = None


class CypherExecutionTrace(BaseModel):
    cypher_query: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float
    rows_returned: int
    graph_name: str
    status: str = "success"  # "success" or "error"
    error_message: Optional[str] = None


class EvidenceReference(BaseModel):
    entity_type: str  # e.g., "Module", "Person", "Commit", "File", "Account", "Transaction"
    entity_id: str
    label: str
    panel_target: Optional[str] = "graph"  # "graph", "code", "simulation", "reviewers", "fraud"
    snippet: Optional[str] = None


class ChatInvestigationRequest(BaseModel):
    question: str = Field(..., description="User's natural language question about the repository or dataset")
    repo_id: Optional[str] = Field(default=None, description="Active repository or source identifier")
    graph_name: Optional[str] = Field(default=None, description="Active FalkorDB graph name")
    conversation_id: Optional[str] = Field(default=None, description="Conversation thread identifier")
    history: List[ChatMessage] = Field(default_factory=list, description="Prior conversation messages")
    target_entity_id: Optional[str] = Field(default=None, description="Currently selected entity in workspace")
    commit_sha: Optional[str] = Field(default=None, description="Source commit SHA snapshot")


class ChatInvestigationResponse(BaseModel):
    conversation_id: str
    repo_id: str
    graph_name: str
    commit_sha: Optional[str] = None
    answer: str
    reasoning_summary: str
    query_traces: List[CypherExecutionTrace] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    provider_status: str  # "gemini", "ollama", "fallback", "not_configured"
    model_name: Optional[str] = None
    suggested_followups: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None


def validate_cypher_readonly(query: str) -> Tuple[bool, str]:
    """Validates that a proposed Cypher query is strictly read-only and safe to execute."""
    cleaned = query.strip()
    # Check for forbidden mutation keywords
    for pattern in _FORBIDDEN_MUTATION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False, f"Query contains forbidden mutation or administrative operation matching: {pattern}"

    # Must start with read/inspection keyword: MATCH, OPTIONAL MATCH, RETURN, CALL db.labels, etc.
    if not re.match(r"^\s*(MATCH|OPTIONAL\s+MATCH|RETURN|UNWIND|WITH|CALL\s+db\.)", cleaned, re.IGNORECASE):
        return False, "Query must start with a read-only keyword (MATCH, RETURN, WITH, CALL db.*)."

    return True, ""


def ensure_bounded_query(query: str, max_limit: int = 25) -> str:
    """Ensures the Cypher query has a strict LIMIT clause and bounded traversals."""
    cleaned = query.strip().rstrip(";")

    # Check for unbounded star traversals like [*] or [r*] and bound them to [*1..3]
    bounded_traversals = re.sub(r"\[([^\]]*)\*\]", r"[\1*1..3]", cleaned)

    # Check if a LIMIT clause is present
    if not re.search(r"\bLIMIT\s+\d+", bounded_traversals, re.IGNORECASE):
        bounded_traversals = f"{bounded_traversals}\nLIMIT {max_limit}"

    return bounded_traversals


class GraphChatService:
    """Coordinates schema discovery, query generation, FalkorDB execution, and LLM grounded synthesis."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or graph_client

    def resolve_context(self, repo_id: Optional[str], graph_name: Optional[str]) -> Tuple[str, str]:
        """Resolves active repo_id and verified server-side graph_name from registry."""
        resolved_repo = repo_id or "repo:local_nexusact"
        rec = repo_registry.get_repository(resolved_repo)

        if rec and rec.graph_name:
            target_graph = rec.graph_name
        elif graph_name and graph_name in ("nexusact_main", "nexusact_fraud_demo", "nexusact_public_data"):
            target_graph = graph_name
        elif rec:
            target_graph = rec.graph_name or "nexusact_main"
        else:
            target_graph = "nexusact_main"

        return resolved_repo, target_graph

    def discover_schema(self, graph_name: str) -> Dict[str, Any]:
        """Discovers labels, relationships, and representative entity names in the active graph."""
        schema: Dict[str, Any] = {
            "graph_name": graph_name,
            "labels": [],
            "relationships": [],
            "sample_modules": [],
            "sample_accounts": [],
            "node_count": 0,
        }

        try:
            # Get node count
            cnt_res = self.client.query("MATCH (n) RETURN count(n) AS cnt", graph_name=graph_name)
            if cnt_res and len(cnt_res) > 0:
                schema["node_count"] = int(cnt_res[0][0])

            # Get sample labels
            lbl_res = self.client.query(
                "MATCH (n) RETURN DISTINCT labels(n)[0] AS lbl, count(n) AS count ORDER BY count DESC LIMIT 10",
                graph_name=graph_name,
            )
            schema["labels"] = [row[0] for row in lbl_res if row and row[0]]

            # Get sample relationships
            rel_res = self.client.query(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS rel, count(r) AS count ORDER BY count DESC LIMIT 10",
                graph_name=graph_name,
            )
            schema["relationships"] = [row[0] for row in rel_res if row and row[0]]

            # If software graph, retrieve top 15 modules
            if "Module" in schema["labels"]:
                mod_res = self.client.query(
                    "MATCH (m:Module) RETURN m.name AS name, m.id AS id LIMIT 15",
                    graph_name=graph_name,
                )
                schema["sample_modules"] = [{"name": r[0], "id": r[1]} for r in mod_res if r]

            # If fraud graph, retrieve sample accounts
            if "Account" in schema["labels"]:
                acc_res = self.client.query(
                    "MATCH (a:Account) RETURN a.id AS id, a.bank AS bank LIMIT 10",
                    graph_name=graph_name,
                )
                schema["sample_accounts"] = [{"id": r[0], "bank": r[1]} for r in acc_res if r]

        except Exception as e:
            logger.warning("Schema discovery encountered error on graph %s: %s", graph_name, e)

        return schema

    def _resolve_target_from_context(
        self,
        question: str,
        target_entity_id: Optional[str],
        history: List[ChatMessage],
        schema: Dict[str, Any],
    ) -> Optional[str]:
        """Resolves target entity from explicit argument, question mention, or prior chat history."""
        # 1. Direct entity in question (e.g., 'fastapi', 'app/main.py', etc.)
        q_lower = question.lower()
        for mod in schema.get("sample_modules", []):
            name = (mod.get("name") or "").lower()
            mid = (mod.get("id") or "").lower()
            if (name and name in q_lower) or (mid and mid in q_lower):
                return mod.get("name") or mod.get("id")

        # 2. Workspace target passed
        if target_entity_id:
            return target_entity_id

        # 3. Pronoun resolution from prior history
        if any(w in q_lower for w in (" it", " this module", " this component", " that module", " its ")):
            for msg in reversed(history):
                for mod in schema.get("sample_modules", []):
                    name = (mod.get("name") or "").lower()
                    if name and name in msg.content.lower():
                        return mod.get("name") or mod.get("id")

        return None

    def plan_cypher_investigation(
        self,
        question: str,
        target: Optional[str],
        schema: Dict[str, Any],
        graph_name: str,
    ) -> List[Tuple[str, Dict[str, Any], str]]:
        """Selects or generates safe read-only Cypher queries tailored to the question and active schema.

        Returns list of (query_string, params, intent_description).
        """
        q_lower = question.lower()
        queries: List[Tuple[str, Dict[str, Any], str]] = []
        labels = schema.get("labels", [])

        # ── Case A: Fraud & Financial Queries ──
        if "Account" in labels or "Transaction" in labels or graph_name == "nexusact_fraud_demo":
            if any(w in q_lower for w in ("cycle", "mule", "fraud", "suspicious", "loop", "circular")):
                q = """
                MATCH path = (a:Account)-[:TRANSFER_TO*3..4]->(a)
                RETURN [n IN nodes(path) | n.id] AS cycle_accounts,
                       length(path) AS cycle_length
                LIMIT 10
                """
                queries.append((q, {}, "Detect circular money flow cycles (layering / muling patterns)"))
            elif any(w in q_lower for w in ("largest", "top", "volume", "amount", "transfers")):
                q = """
                MATCH (a:Account)-[t:TRANSFER_TO]->(b:Account)
                RETURN a.id AS source, b.id AS destination, t.amount AS amount, t.timestamp AS timestamp
                ORDER BY t.amount DESC
                LIMIT 15
                """
                queries.append((q, {}, "Identify high-value transaction transfers"))
            else:
                q = """
                MATCH (a:Account)
                OPTIONAL MATCH (a)-[out:TRANSFER_TO]->()
                OPTIONAL MATCH ()-[inc:TRANSFER_TO]->(a)
                RETURN a.id AS account_id, a.bank AS bank, a.risk_score AS risk_score,
                       count(DISTINCT out) AS outgoing_transfers, count(DISTINCT inc) AS incoming_transfers
                ORDER BY a.risk_score DESC, outgoing_transfers DESC
                LIMIT 15
                """
                queries.append((q, {}, "Retrieve high-risk accounts and transaction degrees"))
            return queries

        # ── Case B: Contributor / Reviewer / Author Questions ──
        if any(w in q_lower for w in ("who", "contributor", "author", "worked on", "commit", "review")):
            if target:
                q = """
                MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:TOUCHES]->(f:File)<-[:CONTAINS]-(m:Module)
                WHERE m.name = $target OR m.id = $target OR m.path CONTAINS $target
                RETURN p.name AS author_name, p.email AS email,
                       count(DISTINCT f) AS files_touched,
                       count(DISTINCT c) AS commits_count,
                       max(c.timestamp) AS last_commit
                ORDER BY commits_count DESC, files_touched DESC
                LIMIT 10
                """
                queries.append((q, {"target": target}, f"Identify authors and contributors touching module '{target}'"))
            else:
                q = """
                MATCH (p:Person)-[:AUTHORED]->(c:Commit)
                OPTIONAL MATCH (c)-[:TOUCHES]->(f:File)
                RETURN p.name AS author_name, p.email AS email,
                       count(DISTINCT f) AS files_touched,
                       count(DISTINCT c) AS commits_count,
                       max(c.timestamp) AS last_commit
                ORDER BY commits_count DESC, files_touched DESC
                LIMIT 10
                """
                queries.append((q, {}, "Retrieve repository-wide top contributors and commit counts"))
            return queries

        # ── Case C: Scenario Simulation / Blast Radius / Breakage Questions ──
        if any(w in q_lower for w in ("break", "remove", "blast radius", "counterfactual", "simulate", "fragile")):
            effective_target = target or (schema.get("sample_modules", [{}])[0].get("name", "app.main"))
            q1 = """
            MATCH (caller:Module)-[:DEPENDS_ON]->(m:Module)
            WHERE m.name = $target OR m.id = $target
            RETURN caller.name AS caller_name, caller.path AS caller_path
            LIMIT 15
            """
            queries.append(
                (q1, {"target": effective_target}, f"Find immediate upstream callers depending on '{effective_target}'")
            )

            q2 = """
            MATCH (m:Module)-[:DEPENDS_ON]->(dep:Module)
            WHERE m.name = $target OR m.id = $target
            RETURN dep.name AS dependency_name, dep.path AS dependency_path
            LIMIT 15
            """
            queries.append(
                (q2, {"target": effective_target}, f"Find downstream dependencies imported by '{effective_target}'")
            )
            return queries

        # ── Case D: Shortest Path / Dependency Routing Questions ──
        if any(w in q_lower for w in ("path", "route", "between", "reach", "flow")):
            # Try to extract two modules
            parts = re.findall(r"['\"]([^'\"]+)['\"]", question)
            if len(parts) >= 2:
                q = """
                MATCH (src:Module), (dst:Module)
                WHERE (src.name = $src OR src.id = $src) AND (dst.name = $dst OR dst.id = $dst)
                MATCH p = shortestPath((src)-[:DEPENDS_ON*..5]->(dst))
                RETURN [n IN nodes(p) | n.name] AS path_nodes, length(p) AS hops
                LIMIT 5
                """
                queries.append(
                    (
                        q,
                        {"src": parts[0], "dst": parts[1]},
                        f"Find shortest dependency path between '{parts[0]}' and '{parts[1]}'",
                    )
                )
                return queries

        # ── Case E: Component Importance / Centrality / Architecture Questions ──
        if any(w in q_lower for w in ("important", "central", "core", "pagerank", "architecture", "overview")):
            q = """
            MATCH (m:Module)
            OPTIONAL MATCH (caller:Module)-[:DEPENDS_ON]->(m)
            OPTIONAL MATCH (m)-[:DEPENDS_ON]->(dep:Module)
            RETURN m.name AS module_name, m.path AS path,
                   count(DISTINCT caller) AS in_degree,
                   count(DISTINCT dep) AS out_degree,
                   (count(DISTINCT caller) + count(DISTINCT dep)) AS total_degree
            ORDER BY in_degree DESC, total_degree DESC
            LIMIT 12
            """
            queries.append((q, {}, "Compute architectural centrality and dependency degrees across repository modules"))
            return queries

        # ── Case F: Default / Targeted Module Inspection ──
        if target:
            q = """
            MATCH (m:Module)
            WHERE m.name = $target OR m.id = $target OR m.path CONTAINS $target
            OPTIONAL MATCH (caller:Module)-[:DEPENDS_ON]->(m)
            OPTIONAL MATCH (m)-[:DEPENDS_ON]->(dep:Module)
            RETURN m.name AS name, m.path AS path,
                   collect(DISTINCT caller.name)[..10] AS callers,
                   collect(DISTINCT dep.name)[..10] AS dependencies,
                   count(DISTINCT caller) AS caller_count,
                   count(DISTINCT dep) AS dep_count
            LIMIT 5
            """
            queries.append((q, {"target": target}, f"Inspect module '{target}' connectivity and callers"))
        else:
            q = """
            MATCH (m:Module)
            OPTIONAL MATCH (caller:Module)-[:DEPENDS_ON]->(m)
            RETURN m.name AS module_name, count(DISTINCT caller) AS caller_count
            ORDER BY caller_count DESC
            LIMIT 10
            """
            queries.append((q, {}, "Retrieve top modules by incoming caller count"))

        return queries

    def execute_query(
        self,
        query: str,
        params: Dict[str, Any],
        graph_name: str,
    ) -> Tuple[List[Any], CypherExecutionTrace]:
        """Safely validates and executes a Cypher query against FalkorDB, returning results and trace."""
        is_safe, err = validate_cypher_readonly(query)
        if not is_safe:
            trace = CypherExecutionTrace(
                cypher_query=query,
                parameters=params,
                execution_time_ms=0.0,
                rows_returned=0,
                graph_name=graph_name,
                status="error",
                error_message=err,
            )
            return [], trace

        bounded_query = ensure_bounded_query(query)
        t_start = time.perf_counter()
        try:
            rows = self.client.query(bounded_query, params=params, graph_name=graph_name)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            trace = CypherExecutionTrace(
                cypher_query=bounded_query,
                parameters=params,
                execution_time_ms=elapsed_ms,
                rows_returned=len(rows) if rows else 0,
                graph_name=graph_name,
                status="success",
            )
            return rows, trace
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning("FalkorDB query failed on graph %s: %s", graph_name, e)
            trace = CypherExecutionTrace(
                cypher_query=bounded_query,
                parameters=params,
                execution_time_ms=elapsed_ms,
                rows_returned=0,
                graph_name=graph_name,
                status="error",
                error_message=str(e),
            )
            return [], trace

    async def answer_question(self, req: ChatInvestigationRequest) -> ChatInvestigationResponse:
        """Processes the natural language question, queries FalkorDB, and returns evidence-grounded response."""
        resolved_repo, target_graph = self.resolve_context(req.repo_id, req.graph_name)
        conv_id = req.conversation_id or f"chat_{uuid.uuid4().hex[:8]}"

        # 1. Discover schema
        schema = self.discover_schema(target_graph)

        # 2. Resolve target entity
        target_entity = self._resolve_target_from_context(req.question, req.target_entity_id, req.history, schema)

        # 3. Plan Cypher queries
        planned_queries = self.plan_cypher_investigation(req.question, target_entity, schema, target_graph)

        # 4. Execute queries against FalkorDB
        query_traces: List[CypherExecutionTrace] = []
        evidence_references: List[EvidenceReference] = []
        raw_results: List[Dict[str, Any]] = []

        for q_str, params, intent in planned_queries:
            rows, trace = self.execute_query(q_str, params, target_graph)
            query_traces.append(trace)

            if trace.status == "success" and rows:
                raw_results.append(
                    {
                        "intent": intent,
                        "query": trace.cypher_query,
                        "rows": rows[:10],
                        "total_rows": len(rows),
                    }
                )

                # Extract evidence items from rows
                for r in rows[:8]:
                    if isinstance(r, list) and len(r) > 0:
                        primary_val = str(r[0])
                        if primary_val and primary_val != "None":
                            # Determine entity type
                            etype = "Module"
                            ptarget = "graph"
                            if "transfer" in q_str.lower() or "account" in q_str.lower():
                                etype = "Account"
                                ptarget = "fraud"
                            elif "authored" in q_str.lower() or "person" in q_str.lower():
                                etype = "Person"
                                ptarget = "reviewers"
                            elif "path" in q_str.lower() and isinstance(r[0], list):
                                etype = "Path"
                                ptarget = "neighborhood"

                            evidence_references.append(
                                EvidenceReference(
                                    entity_type=etype,
                                    entity_id=primary_val,
                                    label=primary_val,
                                    panel_target=ptarget,
                                    snippet=f"Returned in query: {intent}",
                                )
                            )

        # Deduplicate evidence references by entity_id
        seen_ev = set()
        dedup_evidence: List[EvidenceReference] = []
        for ev in evidence_references:
            if ev.entity_id not in seen_ev:
                seen_ev.add(ev.entity_id)
                dedup_evidence.append(ev)

        # 5. Check LLM provider availability
        llm = get_llm_provider()
        is_live_llm = isinstance(llm, GeminiProvider) and llm.is_available

        # 6. Generate answer
        answer = ""
        reasoning = ""
        provider_status = "not_configured"
        model_name = None
        limitations = None

        if is_live_llm and isinstance(llm, GeminiProvider):
            provider_status = "gemini"
            model_name = getattr(llm, "model", "gemini-2.5-flash")
            prompt = f"""You are the NexusAct Graph Intelligence Chat Assistant.
Answer the user's question with technical rigor, grounded STRICTLY in the executed FalkorDB query results below.

Question: "{req.question}"
Active Repository: {resolved_repo}
Active Graph: {target_graph}
Target Entity: {target_entity or "None specified"}

Executed Cypher Queries and Raw Results:
{json.dumps(raw_results, indent=2, default=str)}

RULES:
1. Do NOT invent entities, file paths, dependency counts, or statistics not present in the results.
2. Present evidence clearly with markdown tables or bullet points where appropriate.
3. Explicitly reference the executed Cypher query findings.
4. If results are empty, state that the graph contains no matching evidence and explain what data would be required.
5. Provide a 1-sentence reasoning summary at the start.
"""
            try:
                from google.genai import types

                resp = llm._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                answer = resp.text or ""
                reasoning = (
                    f"Generated via Gemini ({model_name}) grounded in {len(raw_results)} FalkorDB query result(s)."
                )
            except Exception as e:
                logger.warning("Gemini chat generation failed: %s; falling back to deterministic synthesis.", e)
                provider_status = "fallback"
                limitations = (
                    f"Live Gemini generation encountered an API issue: {e}. Provided fallback evidence synthesis."
                )

        if not answer:
            # Deterministic, evidence-grounded fallback synthesis
            provider_status = "not_configured" if not is_live_llm else "fallback"
            model_name = "Deterministic Evidence Synthesizer"
            if not is_live_llm:
                limitations = (
                    "Live Gemini API is not configured. Answer was synthesized deterministically from actual "
                    "FalkorDB Cypher execution results. Configure GEMINI_API_KEY in .env to enable "
                    "generative reasoning."
                )

            answer, reasoning = self._synthesize_deterministic_answer(
                req.question, target_entity, target_graph, raw_results, dedup_evidence
            )

        # 7. Generate context-aware follow-ups
        followups = self._generate_suggested_followups(req.question, target_entity, schema, target_graph)

        return ChatInvestigationResponse(
            conversation_id=conv_id,
            repo_id=resolved_repo,
            graph_name=target_graph,
            commit_sha=req.commit_sha,
            answer=answer,
            reasoning_summary=reasoning,
            query_traces=query_traces,
            evidence_references=dedup_evidence[:8],
            provider_status=provider_status,
            model_name=model_name,
            suggested_followups=followups,
            limitations=limitations,
        )

    def _synthesize_deterministic_answer(
        self,
        question: str,
        target: Optional[str],
        graph_name: str,
        raw_results: List[Dict[str, Any]],
        evidence: List[EvidenceReference],
    ) -> Tuple[str, str]:
        """Constructs an evidence-backed markdown answer directly from query rows when LLM is unconfigured."""
        if not raw_results or all(r.get("total_rows", 0) == 0 for r in raw_results):
            reasoning = "FalkorDB query returned zero matching records for the requested pattern."
            target_str = target or "None"
            answer = (
                f"### Graph Investigation Result for `{graph_name}`\n\n"
                f"NexusAct executed graph traversal queries in FalkorDB, but **no matching records** were found for "
                f'your query: *"{question}"*.\n\n'
                f"**Evidence & Limitations:**\n"
                f"- Active graph: `{graph_name}`\n"
                f"- Target entity resolved: `{target_str}`\n"
                f"- Possible reasons: Target module not present in this snapshot, or relationships uningested.\n\n"
                f"**Recommended next step:** Check the entity name in Graph Explorer or choose a known candidate."
            )
            return answer, reasoning

        sections: List[str] = []
        reasoning = (
            f"FalkorDB executed {len(raw_results)} verified Cypher query pattern(s), "
            "returning real topological evidence."
        )

        sections.append("### Graph-Grounded Investigation Findings\n")
        target_badge = f"  |  **Target:** `{target}`" if target else ""
        sections.append(f'**Question:** *"{question}"*  \n**Active Graph:** `{graph_name}`{target_badge}')
        sections.append("\n---\n")

        for res in raw_results:
            intent = res.get("intent", "Graph Query")
            rows = res.get("rows", [])
            total = res.get("total_rows", len(rows))

            sections.append(f"#### {intent} ({total} record{'s' if total != 1 else ''} found)\n")

            if not rows:
                sections.append("_No matching records found for this pattern._\n")
                continue

            # Format rows as markdown table or bullet list
            first_row = rows[0]
            if isinstance(first_row, list):
                if len(first_row) >= 3:
                    sections.append("| Entity / Node | Metric / Property | Details |")
                    sections.append("| :--- | :--- | :--- |")
                    for row in rows[:8]:
                        c1 = str(row[0]) if len(row) > 0 else ""
                        c2 = str(row[1]) if len(row) > 1 else ""
                        c3 = ", ".join(str(x) for x in row[2:]) if len(row) > 2 else ""
                        sections.append(f"| `{c1}` | {c2} | {c3} |")
                    sections.append("")
                else:
                    for row in rows[:8]:
                        formatted = " -> ".join(f"`{x}`" for x in row if x is not None)
                        sections.append(f"- {formatted}")
                    sections.append("")

        if evidence:
            sections.append("\n**Key Evidence References:**")
            for ev in evidence[:6]:
                panel_label = (ev.panel_target or "graph").title()
                sections.append(f"- **{ev.entity_type}** `{ev.label}` (View in {panel_label} panel)")

        sections.append(
            "\n*All metrics and topological relationships above were directly queried from FalkorDB in real time.*"
        )

        return "\n".join(sections), reasoning

    def _generate_suggested_followups(
        self,
        question: str,
        target: Optional[str],
        schema: Dict[str, Any],
        graph_name: str,
    ) -> List[str]:
        """Generates dynamic follow-up prompts grounded in the active graph capabilities."""
        followups: List[str] = []
        labels = schema.get("labels", [])

        if "Account" in labels or graph_name == "nexusact_fraud_demo":
            followups.append("Which accounts participate in cyclic layering transfers?")
            followups.append("Show high-value transfers between accounts")
            followups.append("What is the highest risk score account in this network?")
        elif "Module" in labels:
            if target:
                followups.append(f"What happens if `{target}` is removed in a simulation?")
                followups.append(f"Who are the top contributors who worked on `{target}`?")
                followups.append(f"Which upstream components call `{target}`?")
            else:
                top_mod = schema.get("sample_modules", [{}])[0].get("name")
                if top_mod:
                    followups.append(f"Why is module `{top_mod}` central to the architecture?")
                    followups.append(f"Simulate removing `{top_mod}` to test blast radius")
                followups.append("Which modules have the highest architectural in-degree?")
                followups.append("Who are the lead contributors across this repository?")

        return followups[:3]
