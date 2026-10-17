"""Phase 15: Live Graph Intelligence and Canonical Source-Snapshot Integration Tests.

Validates:
1. Canonical source snapshot lifecycle, deterministic working-tree fingerprinting, and git ls-remote freshness.
2. Graceful degradation to STALE_SOURCE_UNAVAILABLE on network or remote failure without losing snapshot.
3. Repository isolation: investigations strictly stay within the active repository graph.
4. Consecutive run snapshot consistency (identical commit SHA, fingerprint, and FRESH status).
5. Truthful zero-result, blast radius N/A, and NO_REVIEW_DATA commit author disclosures.
6. Real-world OSV security vulnerability triage with package reachability analysis.
7. Synthetic fraud graph traversal: multi-hop circular cycles, shared device clustering, and verified benign controls.
8. Grounded Code Inspector file-content endpoint with path traversal protection.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.planner import AdaptiveInvestigationAgent
from backend.app.graph.client import graph_client
from backend.app.graph.tools.fraud import (
    FraudInvestigationInput,
    execute_investigate_fraud,
    seed_synthetic_fraud_graph,
)
from backend.app.graph.tools.security_triage import SecurityTriageInput, execute_security_triage
from backend.app.main import app
from backend.app.sources.freshness import (
    compute_working_tree_fingerprint,
    query_remote_github_head,
    source_freshness_service,
)
from backend.app.sources.models import RepositoryRecord, SourceType
from backend.app.sources.registry import repo_registry


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── 1. Canonical Snapshot & Working-Tree Fingerprinting ───────────────────────


def test_working_tree_fingerprint_deterministic(tmp_path: Path):
    """Working tree fingerprint is deterministic across multiple calls with identical files."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("print('hello world')\n", encoding="utf-8")
    (repo_dir / "utils.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (repo_dir / "node_modules").mkdir()
    (repo_dir / "node_modules" / "pkg.js").write_text("ignored", encoding="utf-8")

    commit1, fp1 = compute_working_tree_fingerprint(repo_dir)
    commit2, fp2 = compute_working_tree_fingerprint(repo_dir)

    assert fp1 == fp2, "Fingerprint must be deterministic for identical files"
    assert len(fp1) == 16, "Fingerprint must be a 16-character hex string"


def test_working_tree_fingerprint_detects_changes(tmp_path: Path):
    """Modifying a tracked source file produces a different working tree fingerprint."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    src_file = repo_dir / "main.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    _, fp1 = compute_working_tree_fingerprint(repo_dir)

    # Modify file content
    src_file.write_text("x = 2; y = 3\n", encoding="utf-8")
    _, fp2 = compute_working_tree_fingerprint(repo_dir)

    assert fp1 != fp2, "Fingerprint must change when tracked source code changes"


# ── 2. GitHub Freshness Verification & Network Degradation ───────────────────


def test_query_remote_github_head_success():
    """query_remote_github_head uses git ls-remote to query upstream commit without cloning."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="a1b2c3d4e5f678901234567890abcdef12345678\tHEAD\n",
            returncode=0,
        )
        sha = query_remote_github_head("https://github.com/example/repo")
        assert sha == "a1b2c3d4e5f678901234567890abcdef12345678"


def test_freshness_service_stale_source_unavailable_on_network_failure(tmp_path: Path):
    """If remote upstream is unreachable, status marks STALE_SOURCE_UNAVAILABLE without crashing."""
    repo_id = "repo:test_remote_offline"
    record = RepositoryRecord(
        id=repo_id,
        name="Offline Remote Repo",
        source_type=SourceType.GITHUB,
        canonical_source="https://github.com/mock/offline_repo",
        url_or_path=str(tmp_path),
        graph_name="graph_offline_test",
        default_branch="master",
        commit_sha="1111222233334444555566667777888899990000",
        working_tree_fingerprint="fp_offline",
        active_snapshot_id="snap_offline_v1",
        freshness_status="FRESH",
    )
    repo_registry._repositories[repo_id] = record

    with patch("backend.app.sources.freshness.query_remote_github_head") as mock_query:
        mock_query.side_effect = RuntimeError("Could not resolve host: github.com")

        snapshot = source_freshness_service.check_and_refresh_source(repo_id, force_refresh=True)

        assert snapshot.freshness_status == "STALE_SOURCE_UNAVAILABLE"
        assert snapshot.commit_sha == "1111222233334444555566667777888899990000"
        assert len(snapshot.known_gaps) > 0
        assert "Remote source unavailable" in snapshot.known_gaps[0]


# ── 3. Canonical Snapshot API & Consecutive Run Consistency ──────────────────


def test_consecutive_investigations_maintain_snapshot_consistency(client: TestClient):
    """Consecutive investigations on the same repo return identical snapshot ID and commit SHA."""
    res1 = client.get("/api/v1/ingest/snapshot/repo:local_nexusact")
    assert res1.status_code == 200
    snap1 = res1.json()

    res2 = client.get("/api/v1/ingest/snapshot/repo:local_nexusact")
    assert res2.status_code == 200
    snap2 = res2.json()

    assert snap1["snapshot_id"] == snap2["snapshot_id"]
    assert snap1["commit_sha"] == snap2["commit_sha"]
    assert snap1["working_tree_fingerprint"] == snap2["working_tree_fingerprint"]
    assert snap2["freshness_status"] in ("FRESH", "UPDATED")


@pytest.mark.asyncio
async def test_repository_isolation_rejects_cross_graph_target():
    """An entity that exists only in another graph is rejected as UNRESOLVED in the active repo."""
    agent = AdaptiveInvestigationAgent(client=graph_client)

    # acc:101 exists only in nexusact_fraud_demo, not in nexusact_main
    report = await agent.investigate(
        question="What is the impact of acc:101?",
        repo_id="repo:local_nexusact",
        module_identifier="acc:101",
        investigation_mode="codebase_walkthrough",
    )

    assert report.status == "UNRESOLVED"
    assert report.repository_id == "repo:local_nexusact"
    assert "cannot be resolved" in report.summary.lower() or "unresolved" in (report.unresolved_reason or "").lower()


@pytest.mark.asyncio
async def test_consecutive_investigations_across_three_distinct_graphs(tmp_path: Path):
    """Consecutive investigations across 3 separate graph contexts strictly preserve isolation."""
    agent = AdaptiveInvestigationAgent(client=graph_client)

    # 1. Main local software graph
    rep1 = await agent.investigate(
        question="How do API requests flow into backend.app.main?",
        repo_id="repo:local_nexusact",
        module_identifier="mod:backend.app.main",
        investigation_mode="codebase_walkthrough",
    )
    assert rep1.repository_id == "repo:local_nexusact"
    assert rep1.graph_name == "nexusact_main"

    # 2. Synthetic fraud graph
    rep2 = await agent.investigate(
        question="Investigate circular money movement loops",
        investigation_mode="fraud_demo",
    )
    assert rep2.repository_id == "synthetic_fraud_demo"
    assert rep2.graph_name == "nexusact_fraud_demo"

    # 3. Third isolated repository
    repo3_id = "repo:test_third_graph"
    repo_dir = tmp_path / "third_repo"
    repo_dir.mkdir()
    (repo_dir / "service.py").write_text("def run(): pass\n", encoding="utf-8")
    rec3 = RepositoryRecord(
        id=repo3_id,
        name="Third Test Repo",
        source_type=SourceType.LOCAL,
        canonical_source=str(repo_dir),
        url_or_path=str(repo_dir),
        graph_name="graph_third_test",
        default_branch="master",
        commit_sha="HEAD",
        freshness_status="FRESH",
    )
    repo_registry._repositories[repo3_id] = rec3

    rep3 = await agent.investigate(
        question="Check security triage for third repo",
        repo_id=repo3_id,
        investigation_mode="security_triage",
    )
    assert rep3.repository_id == repo3_id
    assert rep3.graph_name == "graph_third_test"
    assert rep3.graph_name != rep1.graph_name
    assert rep3.graph_name != rep2.graph_name


# ── 4. Truthful Zero-Result, Blast Radius N/A, and NO_REVIEW_DATA ─────────────


@pytest.mark.asyncio
async def test_investigation_blast_radius_na_when_zero_baseline():
    """Agent action proposal presents blast radius as N/A when baseline paths count is 0."""
    agent = AdaptiveInvestigationAgent(client=graph_client)

    report = await agent.investigate(
        question="Investigate blast radius for mock target",
        repo_id="repo:local_nexusact",
        module_identifier="mod:tests.fixtures.typescript_repo.src.services.api",
        investigation_mode="change_impact",
    )

    assert report.status == "COMPLETED"
    assert report.simulation_result is not None

    if report.simulation_result.baseline_paths_count == 0:
        assert report.action_proposal is not None
        body = (
            report.action_proposal.get("body", "")
            if isinstance(report.action_proposal, dict)
            else (report.action_proposal.body if report.action_proposal else "")
        )
        assert "Blast Radius Score:** N/A" in body


@pytest.mark.asyncio
async def test_investigation_reviewer_distinguishes_commit_authors_from_reviews():
    """When PR peer review records are not present, reviewer evidence status is NO_REVIEW_DATA."""
    agent = AdaptiveInvestigationAgent(client=graph_client)

    report = await agent.investigate(
        question="Who has experience with the API service?",
        repo_id="repo:local_nexusact",
        module_identifier="mod:tests.fixtures.typescript_repo.src.services.api",
        investigation_mode="change_impact",
    )

    assert report.reviewer_result is not None
    assert report.reviewer_result.evidence_status == "NO_REVIEW_DATA"
    body = (
        report.action_proposal.get("body", "")
        if isinstance(report.action_proposal, dict)
        else (report.action_proposal.body if report.action_proposal else "")
    )
    assert "PR peer review records unavailable" in body


# ── 5. Real-World OSV Security Vulnerability Triage ──────────────────────────


@pytest.mark.asyncio
async def test_security_triage_osv_live_or_clean():
    """Security triage tool executes against repository manifests and produces structured findings."""
    req = SecurityTriageInput(
        repository_id="repo:local_nexusact",
        manifest_path="package-lock.json",
    )
    result = await execute_security_triage(req)

    assert result.repository_id == "repo:local_nexusact"
    assert result.dependencies_analyzed_count >= 1
    assert result.evidence_status in ("NO_KNOWN_VULNERABILITIES", "CONFIRMED_PUBLIC_EVIDENCE")


# ── 6. Synthetic Fraud Graph Traversal & Benign Controls ─────────────────────


def test_fraud_demo_circular_flow_and_benign_controls():
    """Fraud investigation detects circular routing, shared device, and preserves benign controls."""
    seed_synthetic_fraud_graph()

    output = execute_investigate_fraud(FraudInvestigationInput())

    assert output.risk_indicator == "ELEVATED_SUSPICIOUS_CYCLE"
    assert len(output.patterns_detected) >= 2

    # Circular transfer pattern
    circular = next((p for p in output.patterns_detected if p.pattern_type == "CIRCULAR_TRANSFER_RING"), None)
    assert circular is not None
    assert circular.severity == "HIGH"
    assert circular.total_volume_usd == 27700.0

    # Shared infrastructure pattern with MEDIUM risk
    shared = next((p for p in output.patterns_detected if p.pattern_type == "SHARED_INFRASTRUCTURE"), None)
    assert shared is not None
    assert shared.severity == "MEDIUM"

    # Benign control verification
    assert len(output.benign_controls) >= 2
    benign_ids = {c.account_id for c in output.benign_controls}
    assert "acc:201" in benign_ids
    assert "acc:202" in benign_ids

    # Synthetic disclaimer present
    assert output.synthetic_disclaimer != ""
    assert "synthetic" in output.synthetic_disclaimer.lower()


# ── 7. Grounded Code Inspector Endpoint ──────────────────────────────────────


def test_file_content_endpoint_reads_source(client: TestClient):
    """GET /api/v1/ingest/file-content safely reads file lines with line numbering."""
    res = client.get(
        "/api/v1/ingest/file-content",
        params={
            "repo_id": "repo:local_nexusact",
            "file_path": "backend/app/main.py",
            "start_line": 1,
            "end_line": 15,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["file_path"] == "backend/app/main.py"
    assert data["language"] == "python"
    assert "NexusAct FastAPI Backend Application Entry Point" in data["content"]
    assert data["start_line"] == 1
    assert data["end_line"] == 15


def test_file_content_endpoint_blocks_path_traversal(client: TestClient):
    """GET /api/v1/ingest/file-content rejects path traversal attempts with 400 Bad Request."""
    res = client.get(
        "/api/v1/ingest/file-content",
        params={
            "repo_id": "repo:local_nexusact",
            "file_path": "../../etc/passwd",
        },
    )
    assert res.status_code == 400
    assert "traversal" in res.json()["detail"].lower()
