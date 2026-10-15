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


@router.post("/execute", response_model=ActionExecutionResult)
async def execute_action(payload: ExecuteActionRequest) -> ActionExecutionResult:
    """Executes an approved action strictly validating the approved payload hash."""
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
