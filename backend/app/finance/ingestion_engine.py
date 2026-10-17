"""Financial transaction ingestion engine with schema profiling, validation, and isolated FalkorDB graph writes."""

import csv
import hashlib
import io
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.app.finance.dataset_registry import dataset_registry
from backend.app.finance.models import (
    ColumnMapping,
    DatasetPreviewResponse,
    FinancialDatasetMetadata,
    TransactionRecord,
)
from backend.app.graph.client import FalkorDBClient, graph_client

logger = logging.getLogger("nexusact.finance.ingestion")

MAX_FILE_BYTES = 15 * 1024 * 1024  # 15 MB limit
MAX_TRANSACTION_ROWS = 50_000  # Bound application memory


def suggest_column_mapping(columns: List[str]) -> ColumnMapping:
    """Infers optimal column mappings from column header names using heuristic pattern matching."""
    lower_map = {col.lower().replace("-", "_").replace(" ", "_"): col for col in columns}

    def find_match(patterns: List[str]) -> Optional[str]:
        for pat in patterns:
            for l_col, orig_col in lower_map.items():
                if pat == l_col or l_col.endswith(f"_{pat}") or l_col.startswith(f"{pat}_"):
                    return orig_col
        return None

    src = find_match(["source_account", "sender", "from_account", "origin", "src", "sender_id", "from"]) or (
        columns[0] if len(columns) > 0 else "source_account"
    )
    dst = find_match(
        ["destination_account", "receiver", "to_account", "recipient", "dst", "receiver_id", "to", "target"]
    ) or (columns[1] if len(columns) > 1 else "destination_account")
    amt = find_match(["amount", "amt", "value", "total", "volume", "amount_usd", "tx_amount"]) or (
        columns[2] if len(columns) > 2 else "amount"
    )

    ts = find_match(["timestamp", "datetime", "date", "time", "tx_time", "created_at", "trans_date"])
    tx_id = find_match(["transaction_id", "tx_id", "id", "reference", "ref_id", "transaction_ref"])
    curr = find_match(["currency", "curr", "currency_code"])
    dev = find_match(["device_id", "device", "dev_id", "hardware_id", "device_fingerprint"])
    ip = find_match(["ip_address", "ip", "client_ip", "ip_addr", "remote_ip"])
    merch = find_match(["merchant_id", "merchant", "merchant_name", "vendor", "retailer"])
    label = find_match(["is_fraud", "fraud_label", "label", "fraud", "ground_truth", "is_suspicious"])

    return ColumnMapping(
        source_account=src,
        destination_account=dst,
        amount=amt,
        timestamp=ts,
        transaction_id=tx_id,
        currency=curr,
        device_id=dev,
        ip_address=ip,
        merchant_id=merch,
        ground_truth_label=label,
    )


def preview_dataset(raw_content: str, filename: str) -> DatasetPreviewResponse:
    """Profiles raw CSV or JSON data and returns detected headers, sample rows, and suggested mappings."""
    if len(raw_content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"File size exceeds maximum allowed size of {MAX_FILE_BYTES // (1024 * 1024)} MB.")

    stripped = raw_content.strip()
    is_json = stripped.startswith("[") or stripped.startswith("{")

    detected_columns: List[str] = []
    preview_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if is_json:
        file_type = "JSON"
        try:
            parsed = json.loads(stripped)
            rows = parsed if isinstance(parsed, list) else parsed.get("transactions", parsed.get("records", []))
            if not rows or not isinstance(rows, list):
                raise ValueError("JSON file must contain an array of transaction objects.")
            sample = rows[:5]
            col_set: Dict[str, bool] = {}
            for r in sample:
                if isinstance(r, dict):
                    for k in r.keys():
                        col_set[k] = True
            detected_columns = list(col_set.keys())
            preview_rows = sample
        except Exception as e:
            raise ValueError(f"Invalid JSON format: {e}")
    else:
        file_type = "CSV"
        # Sniff delimiter
        first_line = stripped.split("\n", 1)[0]
        delimiter = "\t" if "\t" in first_line else (";" if ";" in first_line and "," not in first_line else ",")
        reader = csv.DictReader(io.StringIO(stripped), delimiter=delimiter)
        detected_columns = [c.strip() for c in (reader.fieldnames or []) if c and c.strip()]
        if not detected_columns:
            raise ValueError("Could not extract any column headers from CSV file.")
        count = 0
        for row in reader:
            preview_rows.append({k.strip(): (v.strip() if v else "") for k, v in row.items() if k})
            count += 1
            if count >= 5:
                break

    if len(detected_columns) < 3:
        warnings.append("Fewer than 3 columns detected. Valid datasets require source, destination, and amount.")

    suggested = suggest_column_mapping(detected_columns)

    return DatasetPreviewResponse(
        filename=filename,
        file_type=file_type,
        total_preview_rows=len(preview_rows),
        detected_columns=detected_columns,
        suggested_mapping=suggested,
        preview_rows=preview_rows,
        validation_warnings=warnings,
    )


def validate_and_parse_rows(
    raw_content: str,
    mapping: ColumnMapping,
) -> Tuple[List[TransactionRecord], Dict[str, int], List[str]]:
    """
    Validates each record against strict domain criteria:
    - Source and destination account identifiers must be non-empty strings.
    - Amount must be a positive number.
    - Currency normalized to uppercase.
    - Rejection reasons tracked with exact row counts.
    """
    rejections: Dict[str, int] = {}
    warnings: List[str] = []
    valid_records: List[TransactionRecord] = []

    def record_rejection(reason: str):
        rejections[reason] = rejections.get(reason, 0) + 1

    stripped = raw_content.strip()
    is_json = stripped.startswith("[") or stripped.startswith("{")

    raw_rows: List[Dict[str, Any]] = []
    if is_json:
        parsed = json.loads(stripped)
        raw_rows = parsed if isinstance(parsed, list) else parsed.get("transactions", parsed.get("records", []))
    else:
        first_line = stripped.split("\n", 1)[0]
        delimiter = "\t" if "\t" in first_line else (";" if ";" in first_line and "," not in first_line else ",")
        reader = csv.DictReader(io.StringIO(stripped), delimiter=delimiter)
        raw_rows = list(reader)

    if len(raw_rows) > MAX_TRANSACTION_ROWS:
        warnings.append(
            f"Dataset contains {len(raw_rows)} rows. Truncating to {MAX_TRANSACTION_ROWS} rows for memory safety."
        )
        raw_rows = raw_rows[:MAX_TRANSACTION_ROWS]

    seen_tx_ids: Dict[str, bool] = {}

    for idx, row in enumerate(raw_rows, start=1):
        # 1. Source Account
        src = str(row.get(mapping.source_account) or "").strip()
        if not src:
            record_rejection("Missing source account identifier")
            continue

        # 2. Destination Account
        dst = str(row.get(mapping.destination_account) or "").strip()
        if not dst:
            record_rejection("Missing destination account identifier")
            continue

        if src == dst:
            record_rejection("Self-transfer (source equals destination)")
            continue

        # 3. Amount
        amt_raw = str(row.get(mapping.amount) or "").replace("$", "").replace(",", "").strip()
        try:
            amt = float(amt_raw)
            if amt <= 0.0:
                record_rejection("Non-positive transaction amount")
                continue
        except (ValueError, TypeError):
            record_rejection("Non-numeric transaction amount")
            continue

        # 4. Transaction ID (generate deterministic default if omitted)
        tx_id_raw = (
            str(row.get(mapping.transaction_id) or "").strip()
            if mapping.transaction_id and row.get(mapping.transaction_id)
            else ""
        )
        if not tx_id_raw:
            # Deterministic hash of row contents
            tx_id_raw = f"tx_{hashlib.sha256(f'{src}:{dst}:{amt}:{idx}'.encode()).hexdigest()[:12]}"

        if tx_id_raw in seen_tx_ids:
            record_rejection("Duplicate transaction identifier")
            continue
        seen_tx_ids[tx_id_raw] = True

        # 5. Currency
        curr = (
            str(row.get(mapping.currency) or "USD").strip().upper()
            if mapping.currency and row.get(mapping.currency)
            else "USD"
        )

        # 6. Timestamp
        ts = str(row.get(mapping.timestamp) or "").strip() if mapping.timestamp and row.get(mapping.timestamp) else None

        # 7. Device ID
        dev = (
            str(row.get(mapping.device_id) or "").strip() if mapping.device_id and row.get(mapping.device_id) else None
        )

        # 8. IP Address
        ip = (
            str(row.get(mapping.ip_address) or "").strip()
            if mapping.ip_address and row.get(mapping.ip_address)
            else None
        )

        # 9. Merchant ID
        merch = (
            str(row.get(mapping.merchant_id) or "").strip()
            if mapping.merchant_id and row.get(mapping.merchant_id)
            else None
        )

        # 10. Ground Truth Label
        gt_label: Optional[int] = None
        if mapping.ground_truth_label and row.get(mapping.ground_truth_label) is not None:
            raw_gt = str(row.get(mapping.ground_truth_label)).strip().lower()
            if raw_gt in ("1", "true", "fraud", "yes", "suspicious"):
                gt_label = 1
            elif raw_gt in ("0", "false", "benign", "no", "normal"):
                gt_label = 0

        valid_records.append(
            TransactionRecord(
                tx_id=tx_id_raw,
                source_account=src,
                destination_account=dst,
                amount=amt,
                currency=curr,
                timestamp=ts,
                device_id=dev,
                ip_address=ip,
                merchant_id=merch,
                ground_truth_label=gt_label,
                row_number=idx,
            )
        )

    return valid_records, rejections, warnings


def ingest_financial_dataset(
    raw_content: str,
    filename: str,
    dataset_name: str,
    mapping: Optional[ColumnMapping] = None,
    client: Optional[FalkorDBClient] = None,
    is_synthetic: bool = False,
    provenance_note: Optional[str] = None,
) -> FinancialDatasetMetadata:
    """
    Ingests validated financial transaction records into an isolated FalkorDB graph.
    Creates Account, Transaction, Device, IPAddress, Merchant nodes and relationships.
    """
    cli = client or graph_client
    source_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    # Generate unique, validated dataset ID and graph namespace
    clean_slug = re.sub(r"[^a-zA-Z0-9_]", "", dataset_name.lower().replace(" ", "_"))[:16]
    dataset_id = f"fin_{clean_slug}_{uuid.uuid4().hex[:6]}"
    graph_name = dataset_id

    # Detect preview if mapping omitted
    preview = preview_dataset(raw_content, filename)
    active_mapping = mapping or preview.suggested_mapping

    valid_records, rejections, warnings = validate_and_parse_rows(raw_content, active_mapping)

    if not valid_records:
        reasons_str = ", ".join(f"{k}: {v}" for k, v in rejections.items())
        raise ValueError(f"No valid transaction records found in dataset. Rejections: {reasons_str}")

    logger.info(
        "Starting FalkorDB ingestion of %d records into isolated graph '%s'",
        len(valid_records),
        graph_name,
    )

    # 1. Initialize schema indices on isolated graph
    index_queries = [
        "CREATE INDEX FOR (a:Account) ON (a.id)",
        "CREATE INDEX FOR (t:Transaction) ON (t.id)",
        "CREATE INDEX FOR (d:Device) ON (d.id)",
        "CREATE INDEX FOR (ip:IPAddress) ON (ip.id)",
        "CREATE INDEX FOR (m:Merchant) ON (m.id)",
    ]
    for q in index_queries:
        try:
            cli.query(q, graph_name=graph_name)
        except Exception as e:
            logger.debug("Index notice on %s: %s", graph_name, e)

    # 2. Extract unique entity sets for idempotent creation
    accounts: Dict[str, bool] = {}
    devices: Dict[str, bool] = {}
    ips: Dict[str, bool] = {}
    merchants: Dict[str, bool] = {}
    total_volume = 0.0

    gt_counts: Dict[str, int] = {"0": 0, "1": 0}
    has_gt = False

    for rec in valid_records:
        accounts[rec.source_account] = True
        accounts[rec.destination_account] = True
        total_volume += rec.amount
        if rec.device_id:
            devices[rec.device_id] = True
        if rec.ip_address:
            ips[rec.ip_address] = True
        if rec.merchant_id:
            merchants[rec.merchant_id] = True
        if rec.ground_truth_label is not None:
            has_gt = True
            lbl_key = str(rec.ground_truth_label)
            gt_counts[lbl_key] = gt_counts.get(lbl_key, 0) + 1

    # Ingest Accounts
    for acc_id in accounts.keys():
        cli.query(
            "MERGE (a:Account {id: $id}) ON CREATE SET a.name = $name",
            params={"id": acc_id, "name": acc_id},
            graph_name=graph_name,
        )

    # Ingest Devices
    for dev_id in devices.keys():
        cli.query(
            "MERGE (d:Device {id: $id}) ON CREATE SET d.fingerprint = $id",
            params={"id": dev_id},
            graph_name=graph_name,
        )

    # Ingest IP Addresses
    for ip_val in ips.keys():
        cli.query(
            "MERGE (ip:IPAddress {id: $id})",
            params={"id": ip_val},
            graph_name=graph_name,
        )

    # Ingest Merchants
    for merch_id in merchants.keys():
        cli.query(
            "MERGE (m:Merchant {id: $id}) ON CREATE SET m.name = $id",
            params={"id": merch_id},
            graph_name=graph_name,
        )

    # Ingest Transactions & Canonical Directed Relationships
    # (Account)-[:SENDS_TO {tx_id, amount, timestamp, currency}]->(Account)
    # (Account)-[:SENDS]->(Transaction)-[:RECEIVES]->(Account)
    for rec in valid_records:
        # Create Transaction node
        cli.query(
            """
            MERGE (t:Transaction {id: $tx_id})
            ON CREATE SET t.amount = $amount,
                          t.currency = $currency,
                          t.timestamp = $timestamp,
                          t.ground_truth_label = $gt_label
            """,
            params={
                "tx_id": rec.tx_id,
                "amount": rec.amount,
                "currency": rec.currency,
                "timestamp": rec.timestamp or "",
                "gt_label": rec.ground_truth_label if rec.ground_truth_label is not None else -1,
            },
            graph_name=graph_name,
        )

        # Directed canonical transfer edge between accounts
        cli.query(
            """
            MATCH (src:Account {id: $src_id}), (dst:Account {id: $dst_id})
            CREATE (src)-[:SENDS_TO {
                tx_id: $tx_id,
                amount: $amount,
                amount_usd: $amount,
                currency: $currency,
                timestamp: $timestamp
            }]->(dst)
            """,
            params={
                "src_id": rec.source_account,
                "dst_id": rec.destination_account,
                "tx_id": rec.tx_id,
                "amount": rec.amount,
                "currency": rec.currency,
                "timestamp": rec.timestamp or "",
            },
            graph_name=graph_name,
        )

        # Connect transaction node for dual-mode queries
        cli.query(
            """
            MATCH (src:Account {id: $src_id}), (dst:Account {id: $dst_id}), (t:Transaction {id: $tx_id})
            CREATE (src)-[:SENDS]->(t)
            CREATE (t)-[:RECEIVES]->(dst)
            """,
            params={
                "src_id": rec.source_account,
                "dst_id": rec.destination_account,
                "tx_id": rec.tx_id,
            },
            graph_name=graph_name,
        )

        # Connect device if present
        if rec.device_id:
            cli.query(
                """
                MATCH (a:Account {id: $acc_id}), (d:Device {id: $dev_id})
                MERGE (a)-[:USES_DEVICE]->(d)
                """,
                params={"acc_id": rec.source_account, "dev_id": rec.device_id},
                graph_name=graph_name,
            )

        # Connect IP if present
        if rec.ip_address:
            cli.query(
                """
                MATCH (a:Account {id: $acc_id}), (ip:IPAddress {id: $ip})
                MERGE (a)-[:USES_IP]->(ip)
                """,
                params={"acc_id": rec.source_account, "ip": rec.ip_address},
                graph_name=graph_name,
            )

        # Connect merchant if present
        if rec.merchant_id:
            cli.query(
                """
                MATCH (t:Transaction {id: $tx_id}), (m:Merchant {id: $merch_id})
                MERGE (t)-[:AT_MERCHANT]->(m)
                """,
                params={"tx_id": rec.tx_id, "merch_id": rec.merchant_id},
                graph_name=graph_name,
            )

    metadata = FinancialDatasetMetadata(
        dataset_id=dataset_id,
        name=dataset_name,
        filename=filename,
        source_type="sample_benchmark" if is_synthetic else "upload_csv",
        source_hash=source_hash,
        graph_name=graph_name,
        total_rows=len(valid_records) + sum(rejections.values()),
        accepted_rows=len(valid_records),
        rejected_rows=sum(rejections.values()),
        rejection_reasons=rejections,
        schema_mapping=active_mapping.model_dump(),
        columns_detected=preview.detected_columns,
        accounts_count=len(accounts),
        transactions_count=len(valid_records),
        devices_count=len(devices),
        merchants_count=len(merchants),
        ip_addresses_count=len(ips),
        total_volume_usd=round(total_volume, 2),
        has_ground_truth=has_gt,
        ground_truth_stats=gt_counts if has_gt else None,
        status="ACTIVE",
        validation_warnings=warnings,
        is_synthetic=is_synthetic,
        data_provenance_note=provenance_note
        or ("Synthetic AML Benchmark" if is_synthetic else f"Imported from {filename}"),
    )

    dataset_registry.register_dataset(metadata)
    logger.info("Successfully ingested financial dataset '%s' into graph '%s'", dataset_name, graph_name)
    return metadata
