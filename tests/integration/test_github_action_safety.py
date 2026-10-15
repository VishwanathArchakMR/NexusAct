"""Deterministic evaluation tests for Safe GitHub Action Execution.

Covers Section 11 Requirements:
15. Missing GitHub credentials do not break the local investigation.
16. GitHub action proposals are derived from validated findings.
17. A simulated timeout does not cause blind duplicate issue creation.
18. The outcome record reflects actual external read-back results.
Strict binding of approvals to canonical SHA-256 payload hash.
"""

import httpx
import pytest

from backend.app.action.github import (
    ActionState,
    GitHubActionService,
)
from backend.app.core.config import settings
from backend.app.graph.client import graph_client


def test_missing_credentials_allows_proposal_but_blocks_blind_execution():
    """Verify missing GitHub credentials permits local proposal generation but safely blocks external execution."""
    service = GitHubActionService(graph_client)

    proposal = service.propose_issue(
        investigation_id="inv_test_cred",
        title="[NexusAct] Test Architecture Issue",
        body="## Findings\n\nVerified reverse impact: 5 callers.",
    )

    assert proposal.state == ActionState.PROPOSED
    assert proposal.action_id.startswith("act_")
    assert proposal.payload_hash is not None
    # When credentials are not configured, can_execute must be False
    assert proposal.can_execute is False
    assert "GITHUB_TOKEN is not configured" in (proposal.reason or "")


@pytest.mark.asyncio
async def test_hash_mismatch_rejection():
    """Verify that approving a modified/tampered payload hash is immediately rejected."""
    service = GitHubActionService(graph_client)

    proposal = service.propose_issue(
        investigation_id="inv_tamper",
        title="[NexusAct] Original Title",
        body="Original body content.",
    )

    # Attempt to execute with invalid hash
    result = await service.execute_approved_action(
        action_id=proposal.action_id,
        approved_payload_hash="invalid_tampered_hash_0123456789abcdef",
    )

    assert result.state == ActionState.FAILED
    assert "mismatch" in result.message.lower()


@pytest.mark.asyncio
async def test_simulated_timeout_does_not_duplicate_issue():
    """Verify simulated timeout searches for GAF marker and reconciles without creating duplicate."""
    # Temporarily mock credentials in settings
    orig_token = settings.GITHUB_TOKEN
    orig_repo = settings.GITHUB_REPO
    try:
        settings.GITHUB_TOKEN = "test-token"
        settings.GITHUB_REPO = "test-owner/test-repo"

        service = GitHubActionService(graph_client)
        proposal = service.propose_issue(
            investigation_id="inv_timeout_reconcile",
            title="[NexusAct] Timeout Reconcile Test",
            body="Investigation findings.",
        )

        assert "<!-- GAF-ACTION-MARKER:" in proposal.body

        # Mock transport that times out on POST, but on reconciliation GET returns the issue with marker
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and "search" in str(request.url):
                return httpx.Response(200, json={"items": []})
            if request.method == "POST" and "issues" in str(request.url):
                raise httpx.TimeoutException("Network timeout communicating with GitHub")
            if request.method == "GET" and "issues" in str(request.url):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "number": 42,
                            "title": proposal.title,
                            "body": f"Investigation findings.\n\n{proposal.action_id}",
                            "html_url": "https://github.com/test-owner/test-repo/issues/42",
                        }
                    ],
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as mock_http:
            res = await service.execute_approved_action(
                action_id=proposal.action_id,
                approved_payload_hash=proposal.payload_hash,
                custom_http_client=mock_http,
            )

        # Must have reconciled instead of remaining stuck or creating a duplicate!
        assert res.state == ActionState.VERIFIED
        assert res.external_issue_id == 42
        assert res.read_back_verified is True
    finally:
        settings.GITHUB_TOKEN = orig_token
        settings.GITHUB_REPO = orig_repo


@pytest.mark.asyncio
async def test_successful_action_and_independent_readback():
    """Verify that issue creation independently reads back from GitHub
    and records verified outcome in FalkorDB."""

    orig_token = settings.GITHUB_TOKEN
    orig_repo = settings.GITHUB_REPO
    try:
        settings.GITHUB_TOKEN = "test-token"
        settings.GITHUB_REPO = "test-owner/test-repo"

        service = GitHubActionService(graph_client)
        proposal = service.propose_issue(
            investigation_id="inv_readback",
            title="[NexusAct] Verified Readback Test",
            body="Verified body.",
        )

        created_issue = {
            "number": 101,
            "title": proposal.title,
            "body": proposal.body,
            "html_url": "https://github.com/test-owner/test-repo/issues/101",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and "search" in str(request.url):
                return httpx.Response(200, json={"items": []})
            if request.method == "POST" and "issues" in str(request.url):
                return httpx.Response(201, json=created_issue)
            if request.method == "GET" and "/issues/101" in str(request.url):
                return httpx.Response(200, json=created_issue)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as mock_http:
            res = await service.execute_approved_action(
                action_id=proposal.action_id,
                approved_payload_hash=proposal.payload_hash,
                custom_http_client=mock_http,
            )

        assert res.state == ActionState.VERIFIED
        assert res.external_issue_id == 101
        assert res.external_issue_url == "https://github.com/test-owner/test-repo/issues/101"
        assert res.read_back_verified is True

        # Verify ActionOutcome node in FalkorDB
        outcome = graph_client.query(
            "MATCH (a:Action {id: $id})-[:HAS_OUTCOME]->(o:ActionOutcome) RETURN o.external_id, o.url, o.state",
            params={"id": proposal.action_id},
        )
        assert len(outcome) == 1
        assert outcome[0][0] == 101
        assert outcome[0][2] == "VERIFIED"
    finally:
        settings.GITHUB_TOKEN = orig_token
        settings.GITHUB_REPO = orig_repo
