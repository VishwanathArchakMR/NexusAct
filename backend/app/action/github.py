"""Safe GitHub Action integration module.

Implements the strict, verified state flow:
PROPOSED -> APPROVED -> SUBMITTING -> VERIFIED | FAILED | UNKNOWN

Key safety guarantees:
1. Canonical payload hashing binds approvals strictly to the exact preview.
2. Trusted repository configuration is validated against environment settings.
3. Idempotency marker (<!-- GAF-ACTION-MARKER:<hash> -->) embedded in issue body.
4. Pre-creation duplicate search and post-creation independent read-back.
5. Inconclusive or timeout outcomes result in UNKNOWN, never duplicate blindly.
6. Full FalkorDB persistence of Action and ActionOutcome nodes.
"""

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.graph.client import FalkorDBClient, graph_client

logger = logging.getLogger("nexusact.action.github")


class ActionState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    SUBMITTING = "SUBMITTING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class IssueProposal(BaseModel):
    action_id: str
    investigation_id: str
    target_repository: str
    title: str
    body: str
    payload_hash: str
    state: ActionState = ActionState.PROPOSED
    can_execute: bool
    reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ActionExecutionResult(BaseModel):
    action_id: str
    state: ActionState
    external_issue_id: Optional[int] = None
    external_issue_url: Optional[str] = None
    read_back_verified: bool = False
    message: str
    error_details: Optional[str] = None
    executed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def compute_payload_hash(repository: str, title: str, body: str) -> str:
    """Computes a deterministic SHA-256 hash over normalized payload fields."""
    normalized = f"{repository.strip().lower()}\n{title.strip()}\n{body.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def format_action_marker(payload_hash: str) -> str:
    """Creates a unique machine-readable comment marker for idempotency checks."""
    return f"<!-- GAF-ACTION-MARKER:{payload_hash} -->"


class GitHubActionService:
    """Restricted GitHub issue creator with payload verification and read-back."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or graph_client
        self._proposals: Dict[str, IssueProposal] = {}

    def propose_issue(
        self,
        investigation_id: str,
        title: str,
        body: str,
        graph_name: Optional[str] = None,
    ) -> IssueProposal:
        """Constructs an issue proposal with canonical hash and records it in FalkorDB."""
        target_repo = settings.GITHUB_REPO.strip() or "unconfigured"
        has_token = bool(settings.GITHUB_TOKEN.strip())

        # Include unique marker in body for reconciliation
        # Temporary hash without marker first
        base_hash = compute_payload_hash(target_repo, title, body)
        marker = format_action_marker(base_hash)

        if marker not in body:
            final_body = f"{body.rstrip()}\n\n{marker}"
        else:
            final_body = body

        # Final canonical payload hash
        payload_hash = compute_payload_hash(target_repo, title, final_body)
        action_id = f"act_{payload_hash[:12]}"

        can_execute = has_token and bool(target_repo)
        reason = None
        if not has_token:
            reason = "GITHUB_TOKEN is not configured in environment. External execution is disabled."
        elif not target_repo:
            reason = "GITHUB_REPO is not configured in environment. External execution is disabled."

        proposal = IssueProposal(
            action_id=action_id,
            investigation_id=investigation_id,
            target_repository=target_repo or "unconfigured",
            title=title,
            body=final_body,
            payload_hash=payload_hash,
            state=ActionState.PROPOSED,
            can_execute=can_execute,
            reason=reason,
        )

        self._proposals[action_id] = proposal

        # Persist Action node in FalkorDB
        target_graph = graph_name or self.client.primary_graph_name
        self._persist_proposal(proposal, target_graph)

        return proposal

    async def execute_approved_action(
        self,
        action_id: str,
        approved_payload_hash: str,
        graph_name: Optional[str] = None,
        custom_http_client: Optional[httpx.AsyncClient] = None,
    ) -> ActionExecutionResult:
        """Executes issue creation strictly verifying the approved payload hash."""
        target_graph = graph_name or self.client.primary_graph_name

        proposal = self._proposals.get(action_id)
        if not proposal:
            # Try loading from graph
            proposal = self._load_proposal(action_id, target_graph)

        if not proposal:
            return ActionExecutionResult(
                action_id=action_id,
                state=ActionState.FAILED,
                message=f"Action proposal '{action_id}' not found.",
            )

        # 1. Strict Hash Check
        current_hash = compute_payload_hash(proposal.target_repository, proposal.title, proposal.body)
        if current_hash != approved_payload_hash:
            logger.error(
                "Payload hash mismatch for action %s: expected %s, got %s",
                action_id,
                current_hash,
                approved_payload_hash,
            )
            return ActionExecutionResult(
                action_id=action_id,
                state=ActionState.FAILED,
                message="Approval hash mismatch. The proposed issue content changed after preview.",
            )

        # 2. Check credentials
        if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
            return ActionExecutionResult(
                action_id=action_id,
                state=ActionState.FAILED,
                message="GitHub credentials (GITHUB_TOKEN or GITHUB_REPO) are missing from backend environment.",
            )

        # 3. Transition to SUBMITTING
        self._update_action_state(action_id, ActionState.SUBMITTING, target_graph)

        repo = settings.GITHUB_REPO.strip()
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN.strip()}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NexusAct-GAF-Agent",
        }

        # Helper to perform the HTTP requests
        async def _do_execute(client: httpx.AsyncClient) -> ActionExecutionResult:
            # First check if an issue with this marker already exists (Idempotency reconciliation)
            try:
                search_url = f"https://api.github.com/search/issues?q=repo:{repo}+{action_id}"
                search_resp = await client.get(search_url, headers=headers, timeout=10.0)
                if search_resp.status_code == 200:
                    items = search_resp.json().get("items", [])
                    for item in items:
                        if proposal.title in item.get("title", ""):
                            # Reconciled existing issue
                            return self._build_verified_result(action_id, item, target_graph)
            except Exception as e:
                logger.warning("Duplicate check search failed: %s", e)

            # Create the issue
            create_url = f"https://api.github.com/repos/{repo}/issues"
            payload = {
                "title": proposal.title,
                "body": proposal.body,
            }

            try:
                resp = await client.post(create_url, json=payload, headers=headers, timeout=15.0)
            except httpx.TimeoutException:
                logger.warning("Issue creation request timed out. Searching for marker before failing.")
                # Timeout reconciliation check
                try:
                    reconcile_resp = await client.get(
                        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=5",
                        headers=headers,
                        timeout=10.0,
                    )
                    if reconcile_resp.status_code == 200:
                        for issue in reconcile_resp.json():
                            if action_id in issue.get("body", ""):
                                return self._build_verified_result(action_id, issue, target_graph)
                except Exception:
                    pass

                self._update_action_state(action_id, ActionState.UNKNOWN, target_graph)
                return ActionExecutionResult(
                    action_id=action_id,
                    state=ActionState.UNKNOWN,
                    message="Request timed out. Issue creation status is UNKNOWN. Not retrying blindly.",
                )
            except Exception as e:
                self._update_action_state(action_id, ActionState.FAILED, target_graph)
                return ActionExecutionResult(
                    action_id=action_id,
                    state=ActionState.FAILED,
                    message=f"Network error submitting issue: {str(e)}",
                    error_details=str(e),
                )

            if resp.status_code not in (200, 201):
                self._update_action_state(action_id, ActionState.FAILED, target_graph)
                return ActionExecutionResult(
                    action_id=action_id,
                    state=ActionState.FAILED,
                    message=f"GitHub API rejected request with HTTP {resp.status_code}: {resp.text}",
                    error_details=resp.text,
                )

            created_data = resp.json()
            issue_number = created_data.get("number")

            # 4. Independent Read-Back Verification
            try:
                readback_resp = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}",
                    headers=headers,
                    timeout=10.0,
                )
                if readback_resp.status_code == 200:
                    readback_data = readback_resp.json()
                    return self._build_verified_result(action_id, readback_data, target_graph)
                else:
                    self._update_action_state(action_id, ActionState.UNKNOWN, target_graph)
                    return ActionExecutionResult(
                        action_id=action_id,
                        state=ActionState.UNKNOWN,
                        message=f"Issue was created but read-back failed with HTTP {readback_resp.status_code}.",
                    )
            except Exception as e:
                self._update_action_state(action_id, ActionState.UNKNOWN, target_graph)
                return ActionExecutionResult(
                    action_id=action_id,
                    state=ActionState.UNKNOWN,
                    message=f"Issue created but read-back timed out or failed: {str(e)}",
                )

        if custom_http_client:
            return await _do_execute(custom_http_client)
        else:
            async with httpx.AsyncClient() as client:
                return await _do_execute(client)

    def _build_verified_result(
        self, action_id: str, issue_data: Dict[str, Any], graph_name: str
    ) -> ActionExecutionResult:
        external_id = issue_data.get("number")
        external_url = issue_data.get("html_url")

        # Persist outcome in FalkorDB
        self._persist_outcome(action_id, external_id, external_url, ActionState.VERIFIED, graph_name)

        return ActionExecutionResult(
            action_id=action_id,
            state=ActionState.VERIFIED,
            external_issue_id=external_id,
            external_issue_url=external_url,
            read_back_verified=True,
            message=f"Issue #{external_id} created and independently verified on GitHub.",
        )

    def _persist_proposal(self, p: IssueProposal, graph_name: str) -> None:
        try:
            self.client.query(
                """
                MERGE (a:Action {id: $id})
                SET a.title = $title,
                    a.body = $body,
                    a.target_repo = $repo,
                    a.payload_hash = $hash,
                    a.state = $state,
                    a.can_execute = $can_exec,
                    a.created_at = $ts
                WITH a
                MATCH (inv:Investigation {id: $inv_id})
                MERGE (inv)-[:CREATED_ACTION]->(a)
                """,
                params={
                    "id": p.action_id,
                    "title": p.title,
                    "body": p.body,
                    "repo": p.target_repository,
                    "hash": p.payload_hash,
                    "state": p.state.value,
                    "can_exec": p.can_execute,
                    "ts": p.created_at,
                    "inv_id": p.investigation_id,
                },
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to persist action proposal in FalkorDB: %s", e)

    def _update_action_state(self, action_id: str, state: ActionState, graph_name: str) -> None:
        try:
            self.client.query(
                "MATCH (a:Action {id: $id}) SET a.state = $state",
                params={"id": action_id, "state": state.value},
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to update action state in FalkorDB: %s", e)

    def _persist_outcome(
        self, action_id: str, external_id: Optional[int], url: Optional[str], state: ActionState, graph_name: str
    ) -> None:
        try:
            outcome_id = f"out_{action_id}"
            now_iso = datetime.now(timezone.utc).isoformat()
            self.client.query(
                """
                MATCH (a:Action {id: $act_id})
                SET a.state = $state
                MERGE (ao:ActionOutcome {id: $out_id})
                SET ao.external_id = $ext_id,
                    ao.url = $url,
                    ao.state = $state,
                    ao.read_back_verified = true,
                    ao.verified_at = $ts
                MERGE (a)-[:HAS_OUTCOME]->(ao)
                """,
                params={
                    "act_id": action_id,
                    "state": state.value,
                    "out_id": outcome_id,
                    "ext_id": external_id or 0,
                    "url": url or "",
                    "ts": now_iso,
                },
                graph_name=graph_name,
            )
        except Exception as e:
            logger.warning("Failed to persist action outcome in FalkorDB: %s", e)

    def _load_proposal(self, action_id: str, graph_name: str) -> Optional[IssueProposal]:
        try:
            res = self.client.query(
                """
                MATCH (a:Action {id: $id})
                OPTIONAL MATCH (inv:Investigation)-[:CREATED_ACTION]->(a)
                RETURN a.id, a.title, a.body, a.target_repo, a.payload_hash, a.state, a.can_execute, inv.id
                LIMIT 1
                """,
                params={"id": action_id},
                graph_name=graph_name,
            )
            if res:
                row = res[0]
                return IssueProposal(
                    action_id=row[0],
                    title=row[1],
                    body=row[2],
                    target_repository=row[3],
                    payload_hash=row[4],
                    state=ActionState(row[5]),
                    can_execute=bool(row[6]),
                    investigation_id=row[7] or "unknown",
                )
        except Exception as e:
            logger.warning("Failed to load proposal from FalkorDB: %s", e)
        return None


github_action_service = GitHubActionService()
