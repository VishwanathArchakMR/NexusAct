"""Data models for financial transaction ingestion, validation, and graph investigation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Mapping from source file columns to canonical transaction fields."""

    source_account: str = Field(..., description="Column containing sender/source account ID")
    destination_account: str = Field(..., description="Column containing receiver/destination account ID")
    amount: str = Field(..., description="Column containing transaction monetary amount")
    timestamp: Optional[str] = Field(default=None, description="Optional column containing transaction datetime")
    transaction_id: Optional[str] = Field(default=None, description="Optional column containing unique transaction ID")
    currency: Optional[str] = Field(default=None, description="Optional column containing currency (e.g. USD, EUR)")
    device_id: Optional[str] = Field(default=None, description="Optional column containing device fingerprint/ID")
    ip_address: Optional[str] = Field(default=None, description="Optional column containing client IP address")
    merchant_id: Optional[str] = Field(default=None, description="Optional column containing merchant ID or name")
    ground_truth_label: Optional[str] = Field(
        default=None, description="Optional column containing ground-truth fraud label (1/0, true/false)"
    )


class FinancialDatasetMetadata(BaseModel):
    """Metadata describing an ingested financial dataset and its isolated FalkorDB graph."""

    dataset_id: str = Field(..., description="Unique dataset identifier (e.g. fin_9a8b7c)")
    name: str = Field(..., description="Human-readable dataset display name")
    filename: Optional[str] = Field(default=None, description="Original filename if uploaded")
    source_type: str = Field(default="upload_csv", description="Source type: upload_csv, upload_json, sample_benchmark")
    source_hash: str = Field(..., description="SHA-256 fingerprint of the source content")
    graph_name: str = Field(..., description="Isolated FalkorDB graph namespace (e.g. fin_9a8b7c)")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    rejection_reasons: Dict[str, int] = Field(default_factory=dict)
    schema_mapping: Dict[str, Optional[str]] = Field(default_factory=dict)
    columns_detected: List[str] = Field(default_factory=list)
    accounts_count: int = 0
    transactions_count: int = 0
    devices_count: int = 0
    merchants_count: int = 0
    ip_addresses_count: int = 0
    total_volume_usd: float = 0.0
    has_ground_truth: bool = False
    ground_truth_stats: Optional[Dict[str, int]] = None
    status: str = "ACTIVE"  # STAGED | ACTIVE | ERROR
    validation_warnings: List[str] = Field(default_factory=list)
    is_synthetic: bool = False
    data_provenance_note: str = "User-imported financial transaction dataset"


class DatasetPreviewResponse(BaseModel):
    """Preliminary analysis of an uploaded file prior to ingestion."""

    filename: str
    file_type: str
    total_preview_rows: int
    detected_columns: List[str]
    suggested_mapping: ColumnMapping
    preview_rows: List[Dict[str, Any]]
    validation_warnings: List[str] = Field(default_factory=list)


class TransactionRecord(BaseModel):
    """Validated, normalized transaction record ready for FalkorDB ingestion."""

    tx_id: str
    source_account: str
    destination_account: str
    amount: float
    currency: str = "USD"
    timestamp: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    merchant_id: Optional[str] = None
    ground_truth_label: Optional[int] = None  # 1: fraud, 0: benign, None: unlabeled
    row_number: int


class CycleFinding(BaseModel):
    """Closed directed cycle (A -> B -> C -> A) discovered via FalkorDB traversal."""

    cycle_id: str
    hops: int
    participating_accounts: List[str]
    cycle_path: List[str]
    total_volume_usd: float
    min_amount_usd: float
    max_amount_usd: float
    capital_retention_pct: float
    time_window_seconds: Optional[float] = None
    transaction_ids: List[str] = Field(default_factory=list)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    cypher_query_used: str = ""
    description: str = ""


class SharedEntityFinding(BaseModel):
    """Infrastructure sharing (shared device, shared IP) linking distinct accounts."""

    entity_type: str  # Device, IPAddress, Merchant
    entity_id: str
    entity_label: str
    associated_accounts: List[str]
    account_count: int
    cypher_query_used: str = ""
    evidence_note: str = ""


class VelocityFinding(BaseModel):
    """Unusual transaction burst or velocity pattern detected within a time window."""

    account_id: str
    transaction_count: int
    total_volume_usd: float
    time_span_minutes: float
    average_interval_seconds: float
    transaction_ids: List[str] = Field(default_factory=list)
    description: str = ""


class PathFinding(BaseModel):
    """Multi-hop path connecting two target accounts."""

    source_account: str
    destination_account: str
    hops: int
    path_nodes: List[str]
    path_edges: List[Dict[str, Any]] = Field(default_factory=list)
    connected: bool
    cypher_query_used: str = ""


class GroundTruthComparison(BaseModel):
    """Comparison of graph-detected patterns against supplied ground-truth labels."""

    total_labeled_accounts: int
    total_ground_truth_frauds: int
    total_flagged_accounts: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    evaluation_note: str


class BenignControlSummary(BaseModel):
    """Verified non-suspicious accounts serving as baseline controls."""

    account_id: str
    status: str = "BENIGN_NORMAL"
    reason: str
    transaction_count: int
    connected_devices_count: int


class RiskFactorContribution(BaseModel):
    """Transparent mathematical component contributing to the risk score."""

    factor_name: str
    weight: float
    contribution: float
    formula_explanation: str
    supporting_evidence: str


class FraudFinding(BaseModel):
    """Consolidated, evidence-grounded finding produced by FalkorDB graph reasoning."""

    finding_id: str
    category: str  # CIRCULAR_ROUTING, SHARED_INFRASTRUCTURE, VELOCITY_BURST, HIGH_VALUE_ANOMALY
    severity: str  # HIGH, MEDIUM, LOW, INFORMATIONAL
    title: str
    plain_english_summary: str
    affected_accounts: List[str]
    affected_transactions: List[str] = Field(default_factory=list)
    multi_hop_path: Optional[List[str]] = None
    shared_entity_id: Optional[str] = None
    amount_involved_usd: float = 0.0
    cypher_query_used: str
    supporting_records: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: str
    recommended_compliance_action: str


class FinancialInvestigationResult(BaseModel):
    """Complete structured output from a financial graph investigation."""

    investigation_id: str
    dataset_id: str
    dataset_name: str
    graph_name: str
    query_question: str
    status: str = "COMPLETED"  # COMPLETED | NO_DATA_AVAILABLE | FAILED
    investigated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_accounts_analyzed: int = 0
    total_transactions_analyzed: int = 0
    total_volume_analyzed_usd: float = 0.0
    cycles_detected: List[CycleFinding] = Field(default_factory=list)
    shared_entities_detected: List[SharedEntityFinding] = Field(default_factory=list)
    velocity_findings: List[VelocityFinding] = Field(default_factory=list)
    findings: List[FraudFinding] = Field(default_factory=list)
    benign_controls: List[BenignControlSummary] = Field(default_factory=list)
    ground_truth_comparison: Optional[GroundTruthComparison] = None
    risk_score: float = 0.0  # Transparently computed composite score
    risk_indicator: str = "LOW_NORMAL"  # ELEVATED_SUSPICIOUS, MODERATE_REVIEW, LOW_NORMAL, NO_DATA
    risk_factors: List[RiskFactorContribution] = Field(default_factory=list)
    summary: str = ""
    limitations: List[str] = Field(default_factory=list)
    data_provenance_note: str = ""
    is_read_only: bool = True
