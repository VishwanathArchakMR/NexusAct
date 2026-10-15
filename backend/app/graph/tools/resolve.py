"""Natural language entity resolution tool for software graphs."""

import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.schema import LABEL_MODULE

logger = logging.getLogger("nexusact.tools.resolve")

# Stop-words to filter when extracting candidate module tokens from questions
STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "why",
    "where",
    "when",
    "how",
    "if",
    "i",
    "we",
    "you",
    "they",
    "it",
    "this",
    "that",
    "these",
    "those",
    "might",
    "may",
    "can",
    "could",
    "would",
    "should",
    "will",
    "do",
    "does",
    "did",
    "modify",
    "change",
    "update",
    "remove",
    "delete",
    "refactor",
    "touch",
    "affect",
    "affected",
    "depend",
    "depends",
    "dependency",
    "dependencies",
    "dependent",
    "dependents",
    "module",
    "modules",
    "package",
    "packages",
    "file",
    "files",
    "layer",
    "component",
    "service",
    "show",
    "me",
    "tell",
    "find",
    "list",
    "get",
    "inspect",
    "check",
    "explain",
    "code",
    "experience",
    "relevant",
    "structurally",
    "influential",
    "central",
    "connects",
    "happens",
    "graph",
    "database",
    "system",
    "project",
    "repo",
    "repository",
}


class CandidateMatch(BaseModel):
    module_id: str
    module_name: str
    match_type: str = "exact"  # exact, suffix, substring, token


class EntityResolutionOutput(BaseModel):
    query: str
    resolved_id: Optional[str] = None
    resolved_name: Optional[str] = None
    confidence: str = "NONE"  # EXACT, HIGH, AMBIGUOUS, NONE
    candidates: List[CandidateMatch] = Field(default_factory=list)
    clarification_prompt: Optional[str] = None


class ResolveEntityInput(BaseModel):
    query: str = Field(..., description="Entity name or natural language text mentioning a module")
    graph_name: Optional[str] = Field(default=None, description="Target graph name")


def extract_candidate_tokens(text: str) -> List[str]:
    """Extracts plausible entity names and tokens from a free-text question."""
    # Find words with letters/digits/underscores/dots/slashes
    tokens = re.findall(r"[A-Za-z0-9_./\-]+", text)
    candidates = []
    for t in tokens:
        clean = t.strip("./-_,;:'\"")
        if len(clean) >= 2 and clean.lower() not in STOP_WORDS and not clean.isdigit():
            candidates.append(clean)
    return candidates


def execute_resolve_entity(
    payload: ResolveEntityInput,
    client: Optional[FalkorDBClient] = None,
) -> EntityResolutionOutput:
    """
    Resolves natural language references or explicit names to graph modules.
    Confidence levels:
    - EXACT: Exactly one exact match on module name or ID.
    - HIGH: Exactly one match on unique suffix or token.
    - AMBIGUOUS: Multiple matches; lists candidates and prompts user to clarify.
    - NONE: No matching module found.
    """
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name
    query = payload.query.strip()

    # 1. Fetch all modules from graph (typically < 500 modules)
    rows = cli.query(
        f"MATCH (m:{LABEL_MODULE}) RETURN m.id, m.name",
        graph_name=target_graph,
    )
    all_modules = [(r[0], r[1] or r[0]) for r in rows if r]

    if not all_modules:
        return EntityResolutionOutput(
            query=query,
            confidence="NONE",
            clarification_prompt=f"No modules exist in graph '{target_graph}'.",
        )

    # 2. Check direct exact match on query
    exact_matches = []
    q_lower = query.lower()
    for mid, mname in all_modules:
        if q_lower == mid.lower() or q_lower == mname.lower():
            exact_matches.append(CandidateMatch(module_id=mid, module_name=mname, match_type="exact"))

    if len(exact_matches) == 1:
        match = exact_matches[0]
        return EntityResolutionOutput(
            query=query,
            resolved_id=match.module_id,
            resolved_name=match.module_name,
            confidence="EXACT",
            candidates=exact_matches,
        )

    # 3. Check tokens from query
    candidate_tokens = extract_candidate_tokens(query)
    matches_map = {}  # module_id -> CandidateMatch

    for tok in candidate_tokens:
        tok_lower = tok.lower()
        for mid, mname in all_modules:
            mname_lower = mname.lower()
            mid_lower = mid.lower()
            # Exact token match
            if tok_lower == mname_lower or tok_lower == mid_lower:
                matches_map[mid] = CandidateMatch(module_id=mid, module_name=mname, match_type="exact_token")
            # Suffix match (e.g. "billing" matches "services.billing" or "services/billing" or "mod:services/billing")
            elif (
                mname_lower.endswith(f".{tok_lower}")
                or mname_lower.endswith(f"/{tok_lower}")
                or mid_lower.endswith(f"/{tok_lower}")
                or mid_lower.endswith(f".{tok_lower}")
            ):
                if mid not in matches_map:
                    matches_map[mid] = CandidateMatch(module_id=mid, module_name=mname, match_type="suffix")
            # Substring match if token length >= 4
            elif len(tok_lower) >= 4 and (tok_lower in mname_lower or tok_lower in mid_lower):
                if mid not in matches_map:
                    matches_map[mid] = CandidateMatch(module_id=mid, module_name=mname, match_type="substring")

    matches = list(matches_map.values())

    if len(matches) == 1:
        match = matches[0]
        return EntityResolutionOutput(
            query=query,
            resolved_id=match.module_id,
            resolved_name=match.module_name,
            confidence="HIGH",
            candidates=matches,
        )
    elif len(matches) > 1:
        names = [f"'{m.module_name}' ({m.module_id})" for m in matches[:5]]
        names_str = ", ".join(names)
        prompt = (
            f"The query is ambiguous and matched multiple modules: {names_str}. "
            "Please clarify which module you mean."
        )
        return EntityResolutionOutput(
            query=query,
            confidence="AMBIGUOUS",
            candidates=matches[:10],
            clarification_prompt=prompt,
        )
    else:
        return EntityResolutionOutput(
            query=query,
            confidence="NONE",
            clarification_prompt=f"Could not resolve any module matching '{query}' in active graph.",
        )
