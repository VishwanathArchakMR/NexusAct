"""Wikidata entity and relationship connector."""

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

logger = logging.getLogger("nexusact.sources.wikidata")


class WikidataConnector(SourceConnector):
    """Read-only connector for the Wikidata Action API using stable QIDs."""

    SOURCE_ID: ClassVar[str] = "wikidata"
    DISPLAY_NAME: ClassVar[str] = "Wikidata Knowledge Base"
    ENTITY_TYPES: ClassVar[list[str]] = ["Organization", "Person", "Topic", "Model"]
    RELATIONSHIP_TYPES: ClassVar[list[str]] = ["AFFILIATED_WITH", "CREATED_BY", "HAS_TOPIC"]
    ATTRIBUTION: ClassVar[str] = "Wikidata (https://www.wikidata.org) under CC0 License"
    REQUIRES_AUTH: ClassVar[bool] = False
    MAX_RESULTS_PER_QUERY: ClassVar[int] = 10
    REQUEST_TIMEOUT_S: ClassVar[float] = 10.0

    API_BASE: ClassVar[str] = "https://www.wikidata.org/w/api.php"

    # Controlled property mapping
    PROPERTY_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "P108": ("AFFILIATED_WITH", "employer"),
        "P170": ("CREATED_BY", "creator"),
        "P361": ("AFFILIATED_WITH", "part of"),
        "P452": ("HAS_TOPIC", "industry"),
        "P127": ("AFFILIATED_WITH", "owned by"),
    }

    def _http_get(self, params: dict[str, Any]) -> tuple[int, Any]:
        """Performs a bounded GET request to the fixed Wikidata API base."""
        self._rate_limit()
        params["format"] = "json"
        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_BASE}?{query_string}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NexusAct-GAF/1.0 (mailto:nexusact-research@example.org; Wikidata Integration)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT_S) as response:
                status = response.getcode()
                raw_bytes = response.read(self.MAX_RESPONSE_BYTES)
                text = raw_bytes.decode("utf-8", errors="replace")
                data = json.loads(text)
                return status, data
        except Exception as exc:
            logger.warning("Wikidata API request failed: %s", exc)
            raise

    def health_check(self) -> tuple[bool, str]:
        """Probes Wikidata entity search with limit=1."""
        try:
            status, data = self._http_get(
                {
                    "action": "wbsearchentities",
                    "search": "artificial intelligence",
                    "language": "en",
                    "limit": 1,
                }
            )
            if status == 200 and isinstance(data, dict) and "search" in data:
                return True, "Wikidata API reachable"
            return False, f"Unexpected response: {status}"
        except Exception as exc:
            return False, f"Wikidata API unreachable: {exc}"

    def search(self, query: ConnectorQuery) -> ConnectorResult:
        """Searches entities in Wikidata by keyword."""
        limit = min(query.max_results, self.MAX_RESULTS_PER_QUERY)
        records: list[SourceRecord] = []
        coverage_notes: list[str] = []

        try:
            params = {
                "action": "wbsearchentities",
                "search": query.query_text,
                "language": "en",
                "limit": limit,
            }
            _, data = self._http_get(params)
            search_items = data.get("search", []) if isinstance(data, dict) else []

            for item in search_items:
                rec = self._parse_search_item(item)
                if rec:
                    records.append(rec)
        except Exception as exc:
            coverage_notes.append(f"Wikidata entity search failed: {exc}")

        if not records and not coverage_notes:
            coverage_notes.append(f"No Wikidata entities matched query '{query.query_text}'")

        return ConnectorResult(
            source_id=self.SOURCE_ID,
            records=records,
            total_available=len(records),
            coverage_notes=coverage_notes,
            error=coverage_notes[0] if (not records and coverage_notes) else None,
        )

    def fetch_record(self, external_id: str) -> SourceRecord | None:
        """Fetches detailed claims and properties for a QID."""
        clean_qid = external_id.strip().upper()
        if not clean_qid.startswith("Q"):
            return None

        try:
            params = {
                "action": "wbgetentities",
                "ids": clean_qid,
                "languages": "en",
                "props": "labels|descriptions|claims",
            }
            _, data = self._http_get(params)
            entities = data.get("entities", {}) if isinstance(data, dict) else {}
            entity = entities.get(clean_qid)
            if entity and "labels" in entity:
                return self._parse_entity_detail(clean_qid, entity)
        except Exception as exc:
            logger.debug("Failed fetching Wikidata entity '%s': %s", external_id, exc)

        return None

    def _parse_search_item(self, item: dict[str, Any]) -> SourceRecord | None:
        qid = item.get("id")
        if not qid:
            return None

        canonical_url = f"https://www.wikidata.org/wiki/{qid}"
        label = item.get("label") or qid
        description = item.get("description") or ""

        # Infer basic type from description keywords
        desc_lower = description.lower()
        if any(w in desc_lower for w in ("human", "person", "researcher", "scientist", "engineer")):
            entity_type = "Person"
        elif any(w in desc_lower for w in ("organization", "company", "institution", "university", "laboratory")):
            entity_type = "Organization"
        elif any(w in desc_lower for w in ("model", "neural network", "language model", "algorithm")):
            entity_type = "Model"
        else:
            entity_type = "Topic"

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type=entity_type,
            external_id=qid,
            canonical_url=canonical_url,
            data={
                "name": label,
                "description": description,
                "qid": qid,
            },
        )
        rec.compute_hash(json.dumps(item, sort_keys=True))
        return rec

    def _parse_entity_detail(self, qid: str, entity: dict[str, Any]) -> SourceRecord:
        canonical_url = f"https://www.wikidata.org/wiki/{qid}"
        label_obj = entity.get("labels", {}).get("en", {})
        label = label_obj.get("value", qid)
        desc_obj = entity.get("descriptions", {}).get("en", {})
        description = desc_obj.get("value", "")

        relationships: list[SourceRelationship] = []
        claims = entity.get("claims", {})

        for pid, (rel_type, prop_name) in self.PROPERTY_MAP.items():
            if pid in claims:
                for statement in claims[pid][:3]:
                    mainsnak = statement.get("mainsnak", {})
                    datavalue = mainsnak.get("datavalue", {})
                    val_type = datavalue.get("type")
                    if val_type == "wikibase-entityid":
                        target_qid = datavalue.get("value", {}).get("id")
                        if target_qid:
                            rank = statement.get("rank", "normal")
                            has_refs = bool(statement.get("references"))
                            confidence = "HIGH" if (rank == "preferred" or has_refs) else "SUPPORTED"
                            relationships.append(
                                SourceRelationship(
                                    relation_type=rel_type,
                                    source_entity_id=self.namespace_id(qid),
                                    target_entity_id=f"wikidata:{target_qid}",
                                    evidence_field=f"claims.{pid} ({prop_name})",
                                    confidence=confidence,
                                    provenance_url=canonical_url,
                                )
                            )

        desc_lower = description.lower()
        person_keywords = ("human", "person", "researcher", "scientist", "engineer", "psychologist", "professor")
        if any(w in desc_lower for w in person_keywords):
            entity_type = "Person"
        elif any(w in desc_lower for w in ("organization", "company", "institution", "university", "laboratory")):
            entity_type = "Organization"
        elif any(w in desc_lower for w in ("model", "neural network", "language model", "algorithm")):
            entity_type = "Model"
        else:
            entity_type = "Topic"

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type=entity_type,
            external_id=qid,
            canonical_url=canonical_url,
            data={
                "name": label,
                "description": description,
                "qid": qid,
                "claims_count": len(claims),
            },
            relationships=relationships,
        )
        rec.compute_hash(json.dumps(entity, sort_keys=True))
        return rec
