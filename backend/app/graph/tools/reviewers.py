"""Reviewer discovery and developer expertise tool (who_knows)."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.graph.client import FalkorDBClient, graph_client
from backend.app.graph.tools.impact import resolve_module_id

logger = logging.getLogger("nexusact.tools.reviewers")


class ScoreBreakdown(BaseModel):
    files_touched_score: float = Field(
        ..., description="Normalized score based on unique relevant files modified (0.0 to 1.0)"
    )
    recency_score: float = Field(..., description="Recency weighting based on commit activity (0.0 to 1.0)")
    ownership_score: float = Field(..., description="Ownership weight for primary module author or direct reviewer")
    review_history_score: float = Field(..., description="Score from peer code review history (0.0 if unrecorded)")
    files_touched_count: int
    commits_count: int
    days_since_last_touch: int
    has_review_history: bool


class ReviewerCandidate(BaseModel):
    person_id: str
    name: str
    email: str
    composite_score: float = Field(..., description="Normalized final recommendation score (0.0 to 1.0)")
    rank: int
    breakdown: ScoreBreakdown
    rationale: str
    missing_evidence: List[str] = Field(default_factory=list)


class WhoKnowsInput(BaseModel):
    module_identifier: str = Field(..., description="Primary module ID or name to investigate")
    affected_modules: List[str] = Field(
        default_factory=list, description="Optional upstream module IDs identified by trace_impact"
    )
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of candidates to recommend")
    graph_name: Optional[str] = Field(default=None, description="Target graph name")


class WhoKnowsOutput(BaseModel):
    target_module_id: str
    investigated_modules: List[str]
    candidates: List[ReviewerCandidate] = Field(default_factory=list)
    scoring_formula: str = "composite_score = 0.40 * files_touched + 0.30 * recency + 0.20 * ownership + 0.10 * reviews"
    evidence_status: str


def execute_who_knows(
    payload: WhoKnowsInput,
    client: Optional[FalkorDBClient] = None,
) -> WhoKnowsOutput:
    """Executes evidence-based reviewer discovery and scoring."""
    cli = client or graph_client
    target_graph = payload.graph_name or cli.primary_graph_name

    resolved_id = resolve_module_id(cli, payload.module_identifier, graph_name=target_graph)
    if not resolved_id:
        raise ValueError(f"Target module '{payload.module_identifier}' could not be resolved.")

    # Target module plus any affected upstream modules
    target_set = [resolved_id]
    for aff in payload.affected_modules:
        aff_id = resolve_module_id(cli, aff, graph_name=target_graph)
        if aff_id and aff_id not in target_set:
            target_set.append(aff_id)

    # 1. Total files in these modules
    files_query = """
    MATCH (m:Module)-[:CONTAINS]->(f:File)
    WHERE m.id IN $mod_ids
    RETURN count(DISTINCT f) AS total_files
    """
    total_files_res = cli.query(files_query, params={"mod_ids": target_set}, graph_name=target_graph)
    total_files = total_files_res[0][0] if total_files_res and total_files_res[0][0] > 0 else 1

    # 2. Match authors touching files in these modules
    author_query = """
    MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:TOUCHES]->(f:File)<-[:CONTAINS]-(m:Module)
    WHERE m.id IN $mod_ids
    RETURN p.id AS person_id,
           p.name AS name,
           p.email AS email,
           count(DISTINCT f.id) AS files_touched,
           count(DISTINCT c.id) AS commit_count,
           max(c.timestamp) AS last_commit_time
    ORDER BY files_touched DESC, commit_count DESC
    LIMIT 50
    """
    raw_authors = cli.query(author_query, params={"mod_ids": target_set}, graph_name=target_graph)

    # 3. Check for explicit REVIEWS relationships (if present)
    reviewers_map: Dict[str, int] = {}
    try:
        rev_res = cli.query(
            """
            MATCH (p:Person)-[:REVIEWS]->(m:Module)
            WHERE m.id IN $mod_ids
            RETURN p.id AS person_id, count(m) AS rev_count
            """,
            params={"mod_ids": target_set},
            graph_name=target_graph,
        )
        for r_row in rev_res:
            reviewers_map[r_row[0]] = r_row[1]
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    candidates: List[ReviewerCandidate] = []

    for row in raw_authors:
        pid, name, email, touched_cnt, commit_cnt, last_time_str = row[0], row[1], row[2], row[3], row[4], row[5]

        # Files touched normalized score (0.0 - 1.0)
        files_score = min(1.0, float(touched_cnt) / float(total_files))

        # Recency score (decay over days)
        days_ago = 0
        recency_score = 1.0
        if last_time_str:
            try:
                # Parse ISO date
                clean_time = str(last_time_str).replace("Z", "+00:00")
                parsed_time = datetime.fromisoformat(clean_time)
                days_ago = max(0, (now - parsed_time).days)
                recency_score = max(0.1, 1.0 / (1.0 + (days_ago / 30.0)))  # 30-day half-life decay
            except Exception:
                recency_score = 0.5

        # Ownership score (author with highest touched files in target or designated reviewer)
        is_designated_reviewer = pid in reviewers_map
        ownership_score = 1.0 if is_designated_reviewer or (float(touched_cnt) / float(total_files) >= 0.5) else 0.4

        # Review history score
        has_reviews = is_designated_reviewer
        review_score = 1.0 if has_reviews else 0.0

        missing: List[str] = []
        if not has_reviews:
            missing.append("PR peer review records unavailable in local Git log")

        # Composite weighted score
        composite = 0.40 * files_score + 0.30 * recency_score + 0.20 * ownership_score + 0.10 * review_score
        composite = round(min(1.0, max(0.0, composite)), 3)

        breakdown = ScoreBreakdown(
            files_touched_score=round(files_score, 3),
            recency_score=round(recency_score, 3),
            ownership_score=round(ownership_score, 3),
            review_history_score=round(review_score, 3),
            files_touched_count=touched_cnt,
            commits_count=commit_cnt,
            days_since_last_touch=days_ago,
            has_review_history=has_reviews,
        )

        rationale = (
            f"Modified {touched_cnt} relevant file(s) across {commit_cnt} commit(s), "
            f"most recently active {days_ago} day(s) ago."
        )

        candidates.append(
            ReviewerCandidate(
                person_id=pid,
                name=name or email,
                email=email,
                composite_score=composite,
                rank=0,
                breakdown=breakdown,
                rationale=rationale,
                missing_evidence=missing,
            )
        )

    # Sort candidates by composite score descending
    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    top_candidates = candidates[: payload.limit]
    for idx, c in enumerate(top_candidates):
        c.rank = idx + 1

    return WhoKnowsOutput(
        target_module_id=resolved_id,
        investigated_modules=target_set,
        candidates=top_candidates,
        evidence_status="VERIFIED" if top_candidates else "NO_MATCHING_CONTRIBUTORS",
    )
