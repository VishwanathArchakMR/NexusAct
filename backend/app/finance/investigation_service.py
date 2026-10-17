"""Investigation service orchestrating multi-hop graph reasoning and transparent scoring."""

import logging
import uuid
from typing import List, Optional, Set

from backend.app.finance.cypher_engine import (
    evaluate_ground_truth,
    query_benign_controls,
    query_cycles,
    query_shared_entities,
    query_velocity_patterns,
)
from backend.app.finance.dataset_registry import dataset_registry
from backend.app.finance.models import (
    FinancialInvestigationResult,
    FraudFinding,
    RiskFactorContribution,
)
from backend.app.graph.client import FalkorDBClient, graph_client

logger = logging.getLogger("nexusact.finance.investigation")


def run_financial_investigation(
    dataset_id: Optional[str] = None,
    question: Optional[str] = None,
    target_account: Optional[str] = None,
    client: Optional[FalkorDBClient] = None,
) -> FinancialInvestigationResult:
    """
    Executes a comprehensive, evidence-grounded graph investigation against an imported financial dataset.
    Never hallucinates or invents transactions; all findings are backed by executed Cypher queries.
    """
    cli = client or graph_client
    active_ds = dataset_registry.get_dataset(dataset_id) if dataset_id else dataset_registry.get_active_dataset()

    inv_id = f"inv_fin_{uuid.uuid4().hex[:8]}"
    query_text = (
        question or "Investigate potential circular transfer rings, shared infrastructure, and velocity anomalies."
    )

    if not active_ds:
        return FinancialInvestigationResult(
            investigation_id=inv_id,
            dataset_id="",
            dataset_name="No Active Dataset",
            graph_name="",
            query_question=query_text,
            status="NO_DATA_AVAILABLE",
            summary=(
                "No financial transaction dataset is currently loaded in FalkorDB. "
                "Upload a transaction CSV or JSON to initiate graph-native fraud investigation."
            ),
            limitations=["No dataset imported. Import an authorized CSV or JSON dataset to run analysis."],
            data_provenance_note="Awaiting dataset import",
            is_read_only=True,
        )

    graph_name = active_ds.graph_name
    logger.info("Executing financial graph investigation on dataset '%s' (graph: %s)", active_ds.name, graph_name)

    # 1. Query Cycles
    cycles = query_cycles(graph_name, client=cli, min_hops=3, max_hops=5, limit=10)

    # 2. Query Shared Infrastructure
    shared_entities = query_shared_entities(graph_name, client=cli, limit=15)

    # 3. Query Velocity
    velocity = query_velocity_patterns(graph_name, client=cli, min_transfers=3, limit=10)

    # Collect flagged accounts
    flagged_accounts: Set[str] = set()
    for c in cycles:
        flagged_accounts.update(c.participating_accounts)
    for s in shared_entities:
        flagged_accounts.update(s.associated_accounts)

    # 4. Ground Truth Evaluation if labels exist
    gt_comp = evaluate_ground_truth(graph_name, list(flagged_accounts), client=cli)

    # 5. Benign Controls Comparison
    benign_controls = query_benign_controls(graph_name, flagged_accounts, client=cli, limit=5)

    # 6. Generate Transparent Risk Factors
    risk_factors: List[RiskFactorContribution] = []
    total_score = 0.0

    if cycles:
        primary_cycle = cycles[0]
        cycle_contrib = min(0.45, 0.35 + 0.05 * len(cycles))
        cycle_desc_ev = (
            f"{len(cycles)} cycle(s) detected. Primary: {primary_cycle.cycle_id} "
            f"(${primary_cycle.total_volume_usd:,.2f})."
        )
        risk_factors.append(
            RiskFactorContribution(
                factor_name="CIRCULAR_TRANSFER_ROUTING",
                weight=0.45,
                contribution=round(cycle_contrib, 3),
                formula_explanation="Detected closed directed transfer loop across 3+ distinct account nodes.",
                supporting_evidence=cycle_desc_ev,
            )
        )
        total_score += cycle_contrib

    if shared_entities:
        shared_contrib = min(0.30, 0.20 + 0.05 * len(shared_entities))
        shared_ev = f"{len(shared_entities)} shared cluster(s). Identified: {shared_entities[0].entity_label}."
        risk_factors.append(
            RiskFactorContribution(
                factor_name="SHARED_INFRASTRUCTURE",
                weight=0.30,
                contribution=round(shared_contrib, 3),
                formula_explanation="Accounts share physical hardware devices or client IP addresses.",
                supporting_evidence=shared_ev,
            )
        )
        total_score += shared_contrib

    if velocity:
        vel_contrib = min(0.25, 0.15 + 0.03 * len(velocity))
        risk_factors.append(
            RiskFactorContribution(
                factor_name="HIGH_VELOCITY_TRANSFER_BURSTS",
                weight=0.25,
                contribution=round(vel_contrib, 3),
                formula_explanation="Rapid sequential transfers within narrow observation intervals.",
                supporting_evidence=f"{len(velocity)} account(s) exhibit high-frequency transfer patterns.",
            )
        )
        total_score += vel_contrib

    risk_score = round(min(1.0, total_score), 2)
    if risk_score >= 0.65:
        risk_indicator = "ELEVATED_SUSPICIOUS"
    elif risk_score >= 0.30:
        risk_indicator = "MODERATE_REVIEW"
    elif len(flagged_accounts) == 0:
        risk_indicator = "LOW_NORMAL"
    else:
        risk_indicator = "LOW_NORMAL"

    # 7. Synthesize Grounded Findings
    findings: List[FraudFinding] = []

    for c in cycles:
        findings.append(
            FraudFinding(
                finding_id=f"FINDING_{c.cycle_id.upper()}",
                category="CIRCULAR_ROUTING",
                severity="HIGH",
                title=f"Potential Circular Transfer Ring ({c.hops} Hops)",
                plain_english_summary=(
                    f"Accounts {' -> '.join(c.participating_accounts)} participate in a closed loop "
                    f"routing ${c.total_volume_usd:,.2f} with {c.capital_retention_pct:.1f}% capital retention."
                ),
                affected_accounts=c.participating_accounts,
                affected_transactions=c.transaction_ids,
                multi_hop_path=c.cycle_path,
                amount_involved_usd=c.total_volume_usd,
                cypher_query_used=c.cypher_query_used,
                supporting_records=c.transactions,
                limitations=(
                    "Circular transaction topology is an indicator requiring compliance review; "
                    "it is not automatic proof of illicit intent."
                ),
                recommended_compliance_action=(
                    "Perform human compliance review of transaction memos and beneficial ownership "
                    "for participating accounts."
                ),
            )
        )

    for s in shared_entities:
        findings.append(
            FraudFinding(
                finding_id=f"FINDING_SHARED_{s.entity_type.upper()}_{s.entity_id[:8]}",
                category="SHARED_INFRASTRUCTURE",
                severity="MEDIUM",
                title=f"Shared {s.entity_type} Infrastructure Cluster",
                plain_english_summary=(
                    f"{s.account_count} distinct accounts ({', '.join(s.associated_accounts[:4])}) "
                    f"share {s.entity_label}."
                ),
                affected_accounts=s.associated_accounts,
                shared_entity_id=s.entity_id,
                cypher_query_used=s.cypher_query_used,
                supporting_records=[
                    {"entity_type": s.entity_type, "entity_id": s.entity_id, "accounts": s.associated_accounts}
                ],
                limitations=(
                    "Shared devices or IPs can occur legitimately in corporate networks, "
                    "shared households, or via public VPN services."
                ),
                recommended_compliance_action=(
                    "Check whether accounts share common household or business identity before taking risk actions."
                ),
            )
        )

    summary_text = (
        f"FalkorDB graph intelligence analyzed {active_ds.accounts_count} accounts and "
        f"{active_ds.transactions_count} transactions in '{active_ds.name}'. "
        f"Detected {len(cycles)} circular routing ring(s) and {len(shared_entities)} shared infrastructure cluster(s). "
        f"Calculated risk indicator: {risk_indicator} (Score: {risk_score})."
    )

    limitations = [
        "Read-only investigation: NexusAct does not execute account freezes, funds reversals, or external actions.",
        "Graph findings reflect topological structures in the uploaded dataset; external KYC context required.",
    ]
    if not active_ds.has_ground_truth:
        limitations.append(
            "Ground-truth fraud labels were absent in this dataset; findings represent algorithmic risk indicators."
        )

    return FinancialInvestigationResult(
        investigation_id=inv_id,
        dataset_id=active_ds.dataset_id,
        dataset_name=active_ds.name,
        graph_name=graph_name,
        query_question=query_text,
        status="COMPLETED",
        total_accounts_analyzed=active_ds.accounts_count,
        total_transactions_analyzed=active_ds.transactions_count,
        total_volume_analyzed_usd=active_ds.total_volume_usd,
        cycles_detected=cycles,
        shared_entities_detected=shared_entities,
        velocity_findings=velocity,
        findings=findings,
        benign_controls=benign_controls,
        ground_truth_comparison=gt_comp,
        risk_score=risk_score,
        risk_indicator=risk_indicator,
        risk_factors=risk_factors,
        summary=summary_text,
        limitations=limitations,
        data_provenance_note=active_ds.data_provenance_note,
        is_read_only=True,
    )


execute_financial_investigation = run_financial_investigation
