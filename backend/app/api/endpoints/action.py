"""Action execution API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.action.github import (
    ActionExecutionResult,
    IssueProposal,
    github_action_service,
)
from backend.app.core.config import settings

logger = logging.getLogger("nexusact.api.action")
router = APIRouter(prefix="/action", tags=["Action Execution"])


class ProposeActionRequest(BaseModel):
    investigation_id: str = Field(..., description="Source investigation ID")
    title: str = Field(..., description="Proposed issue title")
    body: str = Field(..., description="Proposed issue body")
    graph_name: Optional[str] = None


class ExecuteActionRequest(BaseModel):
    action_id: str = Field(..., description="Action ID to execute")
    approved_payload_hash: str = Field(..., description="Approved canonical payload hash")
    graph_name: Optional[str] = None


class SaveInternalActionRequest(BaseModel):
    action_id: str = Field(..., description="Action ID to save internally")
    graph_name: Optional[str] = None


@router.post("/propose", response_model=IssueProposal)
def propose_action(payload: ProposeActionRequest) -> IssueProposal:
    """Creates a proposed GitHub action and calculates its canonical approval hash."""
    try:
        proposal = github_action_service.propose_issue(
            investigation_id=payload.investigation_id,
            title=payload.title,
            body=payload.body,
            graph_name=payload.graph_name,
        )
        return proposal
    except Exception as e:
        logger.error("Failed to propose action: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-internal", response_model=IssueProposal)
def save_internal_action(payload: SaveInternalActionRequest) -> IssueProposal:
    """Saves a proposed action as a persistent internal follow-up task in FalkorDB."""
    try:
        saved = github_action_service.save_internal_proposal(
            action_id=payload.action_id,
            graph_name=payload.graph_name,
        )
        return saved
    except Exception as e:
        logger.error("Failed to save internal action: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ActionExecutionResult)
async def execute_action(payload: ExecuteActionRequest) -> ActionExecutionResult:
    """Executes an approved action strictly validating the approved payload hash."""
    if settings.PUBLIC_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail=(
                "External action execution is disabled in public demo mode. "
                "Internal review and proposal inspection remain available."
            ),
        )
    try:
        result = await github_action_service.execute_approved_action(
            action_id=payload.action_id,
            approved_payload_hash=payload.approved_payload_hash,
            graph_name=payload.graph_name,
        )
        return result
    except Exception as e:
        logger.error("Failed to execute action: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
