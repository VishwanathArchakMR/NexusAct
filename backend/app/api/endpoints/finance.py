"""FastAPI router for financial dataset ingestion, profiling, and graph investigation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend.app.finance.cypher_engine import query_financial_subgraph
from backend.app.finance.dataset_registry import dataset_registry
from backend.app.finance.ingestion_engine import (
    ingest_financial_dataset,
    preview_dataset,
)
from backend.app.finance.investigation_service import run_financial_investigation
from backend.app.finance.models import (
    ColumnMapping,
    DatasetPreviewResponse,
    FinancialDatasetMetadata,
    FinancialInvestigationResult,
)

logger = logging.getLogger("nexusact.api.finance")
router = APIRouter(prefix="/finance", tags=["Financial Graph Investigation"])


class PreviewRequest(BaseModel):
    raw_content: str = Field(..., description="Raw CSV or JSON text content")
    filename: str = Field(default="transactions.csv", description="Filename for profiling")


class IngestTextRequest(BaseModel):
    raw_content: str = Field(..., description="Raw CSV or JSON text content")
    filename: str = Field(default="transactions.csv", description="Filename")
    dataset_name: str = Field(..., description="Display name for the dataset")
    mapping: Optional[ColumnMapping] = Field(default=None, description="Optional column mapping")


class InvestigateRequest(BaseModel):
    dataset_id: Optional[str] = Field(default=None, description="Target dataset ID")
    question: Optional[str] = Field(default=None, description="Investigation inquiry or question")
    target_account: Optional[str] = Field(default=None, description="Optional account to focus on")


@router.post("/preview", response_model=DatasetPreviewResponse)
async def preview_financial_file(
    file: Optional[UploadFile] = File(None),
    payload: Optional[PreviewRequest] = None,
) -> DatasetPreviewResponse:
    """Profiles uploaded transaction file and returns detected columns, sample rows, and suggested mappings."""
    if file:
        content = (await file.read()).decode("utf-8", errors="replace")
        fname = file.filename or "uploaded.csv"
    elif payload and payload.raw_content:
        content = payload.raw_content
        fname = payload.filename
    else:
        raise HTTPException(status_code=400, detail="Must provide either a file upload or raw_content in body.")

    try:
        return preview_dataset(content, fname)
    except Exception as e:
        logger.warning("Error previewing financial dataset: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest", response_model=FinancialDatasetMetadata)
async def ingest_financial_file(
    file: Optional[UploadFile] = File(None),
    dataset_name: Optional[str] = Form(None),
    mapping_json: Optional[str] = Form(None),
    payload: Optional[IngestTextRequest] = None,
) -> FinancialDatasetMetadata:
    """Validates and ingests financial transaction records into an isolated FalkorDB graph."""
    if file:
        content = (await file.read()).decode("utf-8", errors="replace")
        fname = file.filename or "uploaded.csv"
        ds_name = dataset_name or Path(fname).stem
        mapping_obj: Optional[ColumnMapping] = None
        if mapping_json:
            try:
                mapping_obj = ColumnMapping(**json.loads(mapping_json))
            except Exception as e:
                logger.warning("Could not parse mapping JSON: %s", e)
    elif payload:
        content = payload.raw_content
        fname = payload.filename
        ds_name = payload.dataset_name
        mapping_obj = payload.mapping
    else:
        raise HTTPException(status_code=400, detail="Must provide either a file upload or body payload.")

    try:
        metadata = ingest_financial_dataset(
            raw_content=content,
            filename=fname,
            dataset_name=ds_name,
            mapping=mapping_obj,
            is_synthetic=False,
            provenance_note=f"Uploaded by user: {fname}",
        )
        return metadata
    except Exception as e:
        logger.warning("Ingestion error for %s: %s", ds_name, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/load-sample", response_model=FinancialDatasetMetadata)
async def load_sample_benchmark_dataset() -> FinancialDatasetMetadata:
    """Loads the bundled legitimate anonymized AML benchmark dataset with transparent provenance."""
    sample_path = (
        Path(__file__).resolve().parent.parent.parent / "finance" / "samples" / "aml_transaction_benchmark.csv"
    )
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample benchmark dataset file not found.")

    content = sample_path.read_text(encoding="utf-8")
    metadata = ingest_financial_dataset(
        raw_content=content,
        filename="aml_transaction_benchmark.csv",
        dataset_name="AML Synthetic Benchmark (Anonymized)",
        is_synthetic=True,
        provenance_note="Standard AML topological benchmark with 3-hop circular routing and shared device cluster",
    )
    return metadata


@router.get("/datasets", response_model=List[FinancialDatasetMetadata])
async def list_financial_datasets() -> List[FinancialDatasetMetadata]:
    """Lists all registered financial datasets."""
    return dataset_registry.list_datasets()


@router.get("/datasets/active", response_model=Optional[FinancialDatasetMetadata])
async def get_active_financial_dataset() -> Optional[FinancialDatasetMetadata]:
    """Returns metadata for the currently active financial dataset."""
    ds = dataset_registry.get_active_dataset()
    if not ds:
        return None
    return ds


@router.post("/datasets/{dataset_id}/activate")
async def activate_financial_dataset(dataset_id: str) -> Dict[str, Any]:
    """Sets the active financial dataset ID."""
    success = dataset_registry.set_active_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return {"status": "ACTIVATED", "dataset_id": dataset_id}


@router.delete("/datasets/{dataset_id}")
async def delete_financial_dataset(dataset_id: str) -> Dict[str, Any]:
    """Deletes a financial dataset and drops its isolated FalkorDB graph."""
    success = dataset_registry.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return {"status": "DELETED", "dataset_id": dataset_id}


@router.post("/investigate", response_model=FinancialInvestigationResult)
async def investigate_financial_graph(payload: InvestigateRequest) -> FinancialInvestigationResult:
    """Executes a real graph investigation on the specified or active financial dataset."""
    result = run_financial_investigation(
        dataset_id=payload.dataset_id,
        question=payload.question,
        target_account=payload.target_account,
    )
    return result


@router.get("/datasets/{dataset_id}/subgraph")
async def get_financial_subgraph(
    dataset_id: str,
    center_id: Optional[str] = Query(None, description="Optional center entity ID"),
    limit: int = Query(80, ge=1, le=250),
) -> Dict[str, Any]:
    """Returns visual subgraph nodes and edges for the specified dataset's isolated graph."""
    ds = dataset_registry.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return query_financial_subgraph(ds.graph_name, center_id=center_id, limit=limit)


@router.get("/template", response_class=PlainTextResponse)
async def download_csv_template() -> str:
    """Returns a downloadable CSV template with standard header comments and column names."""
    template = (
        "# NexusAct Financial Transaction Import Template\n"
        "# Required columns: source_account, destination_account, amount\n"
        "# Optional columns: transaction_id, timestamp, currency, device_id, ip_address, merchant_id, is_fraud\n"
        "transaction_id,source_account,destination_account,amount,currency,timestamp,device_id,ip_address,merchant_id,is_fraud\n"
        "TX_001,ACC_101,ACC_102,9500.00,USD,2026-10-14T09:15:00Z,DEV_IPHONE_01,198.51.100.42,,1\n"
        "TX_002,ACC_102,ACC_103,9200.00,USD,2026-10-14T10:30:00Z,DEV_LAPTOP_02,198.51.100.42,,1\n"
        "TX_003,ACC_103,ACC_101,9000.00,USD,2026-10-14T11:45:00Z,DEV_IPHONE_01,203.0.113.19,,1\n"
        "TX_004,ACC_201,ACC_202,45.50,USD,2026-10-14T12:00:00Z,DEV_PIXEL_03,192.0.2.88,MERCH_CAFE,0\n"
    )
    return template
