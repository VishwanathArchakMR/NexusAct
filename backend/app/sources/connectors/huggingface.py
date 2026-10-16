"""Hugging Face Hub public metadata source connector."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, ClassVar

from backend.app.sources.connector_registry import (
    ConnectorQuery,
    ConnectorResult,
    SourceConnector,
    SourceRecord,
    SourceRelationship,
)

logger = logging.getLogger("nexusact.sources.huggingface")


class HuggingFaceConnector(SourceConnector):
    """Read-only connector for the Hugging Face Hub public metadata API."""

    SOURCE_ID: ClassVar[str] = "huggingface"
    DISPLAY_NAME: ClassVar[str] = "Hugging Face Hub"
    ENTITY_TYPES: ClassVar[list[str]] = ["Model", "Dataset"]
    RELATIONSHIP_TYPES: ClassVar[list[str]] = ["USES_DATASET", "CREATED_BY", "HOSTED_ON"]
    ATTRIBUTION: ClassVar[str] = "Hugging Face Hub (https://huggingface.co)"
    REQUIRES_AUTH: ClassVar[bool] = False
    MAX_RESULTS_PER_QUERY: ClassVar[int] = 15
    REQUEST_TIMEOUT_S: ClassVar[float] = 10.0

    API_BASE: ClassVar[str] = "https://huggingface.co/api/"

    def _http_get(self, path: str, params: dict[str, Any], timeout: float | None = None) -> tuple[int, Any]:
        """Performs a bounded GET request to the fixed Hugging Face API base."""
        self._rate_limit()
        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_BASE}{path}?{query_string}" if query_string else f"{self.API_BASE}{path}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NexusAct-GAF/1.0 (Public Research Investigation; https://github.com/VishwanathArchakMR/NexusAct)",
                "Accept": "application/json",
            },
        )
        t_out = timeout or self.REQUEST_TIMEOUT_S
        try:
            with urllib.request.urlopen(req, timeout=t_out) as response:
                status = response.getcode()
                raw_bytes = response.read(self.MAX_RESPONSE_BYTES)
                text = raw_bytes.decode("utf-8", errors="replace")
                data = json.loads(text)
                return status, data
        except Exception as exc:
            logger.warning("Hugging Face API request failed for %s: %s", path, exc)
            raise

    def health_check(self) -> tuple[bool, str]:
        """Probes the public Hugging Face models endpoint with limit=1 and fast timeout."""
        try:
            status, data = self._http_get("models", {"limit": 1}, timeout=3.0)
            if status == 200 and isinstance(data, list):
                return True, "Hugging Face Hub API reachable"
            return False, f"Unexpected response code: {status}"
        except Exception as exc:
            return False, f"Hugging Face Hub unreachable: {exc}"

    def search(self, query: ConnectorQuery) -> ConnectorResult:
        """Searches public models and datasets within configured limits."""
        limit = min(query.max_results, self.MAX_RESULTS_PER_QUERY)
        records: list[SourceRecord] = []
        coverage_notes: list[str] = []
        fetch_models = not query.entity_types or "Model" in query.entity_types
        fetch_datasets = not query.entity_types or "Dataset" in query.entity_types

        # 1. Search Models
        if fetch_models:
            try:
                _, models = self._http_get("models", {"search": query.query_text, "limit": limit, "full": "false"})
                if isinstance(models, list):
                    for item in models:
                        rec = self._parse_model_item(item)
                        if rec:
                            records.append(rec)
            except Exception as exc:
                coverage_notes.append(f"Model search partially unavailable: {exc}")

        # 2. Search Datasets
        if fetch_datasets and len(records) < limit:
            rem_limit = limit - len(records)
            try:
                _, datasets = self._http_get(
                    "datasets", {"search": query.query_text, "limit": rem_limit, "full": "false"}
                )
                if isinstance(datasets, list):
                    for item in datasets:
                        rec = self._parse_dataset_item(item)
                        if rec:
                            records.append(rec)
            except Exception as exc:
                coverage_notes.append(f"Dataset search partially unavailable: {exc}")

        if not records and not coverage_notes:
            coverage_notes.append(f"No Hugging Face records matched query '{query.query_text}'")

        return ConnectorResult(
            source_id=self.SOURCE_ID,
            records=records,
            total_available=len(records),
            coverage_notes=coverage_notes,
            error=coverage_notes[0] if (not records and coverage_notes) else None,
        )

    def fetch_record(self, external_id: str) -> SourceRecord | None:
        """Fetches detailed metadata for a specific model or dataset ID."""
        try:
            _, data = self._http_get(f"models/{urllib.parse.quote(external_id, safe='')}", {})
            if isinstance(data, dict) and "id" in data:
                return self._parse_model_item(data)
        except Exception:
            pass

        try:
            _, data = self._http_get(f"datasets/{urllib.parse.quote(external_id, safe='')}", {})
            if isinstance(data, dict) and "id" in data:
                return self._parse_dataset_item(data)
        except Exception:
            pass

        return None

    def _parse_model_item(self, item: dict[str, Any]) -> SourceRecord | None:
        model_id = item.get("id") or item.get("_id")
        if not model_id:
            return None

        canonical_url = f"https://huggingface.co/{model_id}"
        author = item.get("author") or (model_id.split("/")[0] if "/" in model_id else None)
        tags = item.get("tags") or []
        pipeline_tag = item.get("pipeline_tag") or ""
        likes = item.get("likes", 0)
        downloads = item.get("downloads", 0)

        relationships: list[SourceRelationship] = []
        # Creator relation
        if author:
            relationships.append(
                SourceRelationship(
                    relation_type="CREATED_BY",
                    source_entity_id=self.namespace_id(model_id),
                    target_entity_id=f"org:huggingface:{author}",
                    evidence_field="author",
                    confidence="SUPPORTED",
                    provenance_url=canonical_url,
                )
            )

        # Dataset references from tags (e.g. 'dataset:squad')
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("dataset:"):
                ds_name = tag.split("dataset:", 1)[1]
                if ds_name:
                    relationships.append(
                        SourceRelationship(
                            relation_type="USES_DATASET",
                            source_entity_id=self.namespace_id(model_id),
                            target_entity_id=f"huggingface:{ds_name}",
                            evidence_field="tags.dataset",
                            confidence="SUPPORTED",
                            provenance_url=canonical_url,
                        )
                    )

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type="Model",
            external_id=model_id,
            canonical_url=canonical_url,
            data={
                "name": model_id,
                "author": author,
                "pipeline_tag": pipeline_tag,
                "tags": tags[:10],
                "likes": likes,
                "downloads": downloads,
            },
            relationships=relationships,
        )
        rec.compute_hash(json.dumps(item, sort_keys=True))
        return rec

    def _parse_dataset_item(self, item: dict[str, Any]) -> SourceRecord | None:
        ds_id = item.get("id") or item.get("_id")
        if not ds_id:
            return None

        canonical_url = f"https://huggingface.co/datasets/{ds_id}"
        author = item.get("author") or (ds_id.split("/")[0] if "/" in ds_id else None)
        tags = item.get("tags") or []
        downloads = item.get("downloads", 0)

        relationships: list[SourceRelationship] = []
        if author:
            relationships.append(
                SourceRelationship(
                    relation_type="CREATED_BY",
                    source_entity_id=self.namespace_id(ds_id),
                    target_entity_id=f"org:huggingface:{author}",
                    evidence_field="author",
                    confidence="SUPPORTED",
                    provenance_url=canonical_url,
                )
            )

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type="Dataset",
            external_id=ds_id,
            canonical_url=canonical_url,
            data={
                "name": ds_id,
                "author": author,
                "tags": tags[:10],
                "downloads": downloads,
            },
            relationships=relationships,
        )
        rec.compute_hash(json.dumps(item, sort_keys=True))
        return rec
