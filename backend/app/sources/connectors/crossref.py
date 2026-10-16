"""Crossref REST API publication and DOI connector."""

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

logger = logging.getLogger("nexusact.sources.crossref")


class CrossrefConnector(SourceConnector):
    """Read-only connector for the Crossref REST API for DOI metadata and citations."""

    SOURCE_ID: ClassVar[str] = "crossref"
    DISPLAY_NAME: ClassVar[str] = "Crossref Metadata API"
    ENTITY_TYPES: ClassVar[list[str]] = ["Paper", "Person", "Organization"]
    RELATIONSHIP_TYPES: ClassVar[list[str]] = ["AUTHORED", "AFFILIATED_WITH", "CITES", "FUNDED_BY"]
    ATTRIBUTION: ClassVar[str] = "Crossref (https://www.crossref.org)"
    REQUIRES_AUTH: ClassVar[bool] = False
    MAX_RESULTS_PER_QUERY: ClassVar[int] = 10
    REQUEST_TIMEOUT_S: ClassVar[float] = 10.0

    API_BASE: ClassVar[str] = "https://api.crossref.org/"

    def _http_get(self, path: str, params: dict[str, Any], timeout: float | None = None) -> tuple[int, Any]:
        """Performs a bounded GET request to the fixed Crossref API base."""
        self._rate_limit()
        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_BASE}{path}?{query_string}" if query_string else f"{self.API_BASE}{path}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NexusAct-GAF/1.0 (mailto:nexusact-research@example.org; Crossref Integration)",
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
            logger.warning("Crossref API request failed for %s: %s", path, exc)
            raise

    def health_check(self) -> tuple[bool, str]:
        """Probes Crossref works endpoint with rows=1 and fast timeout."""
        try:
            status, data = self._http_get("works", {"rows": 1}, timeout=3.0)
            if status == 200 and isinstance(data, dict) and "message" in data:
                return True, "Crossref API reachable"
            return False, f"Unexpected response code: {status}"
        except Exception as exc:
            return False, f"Crossref API unreachable: {exc}"

    def search(self, query: ConnectorQuery) -> ConnectorResult:
        """Searches works in Crossref by free-text title or terms."""
        limit = min(query.max_results, self.MAX_RESULTS_PER_QUERY)
        records: list[SourceRecord] = []
        coverage_notes: list[str] = []

        try:
            params = {
                "query": query.query_text,
                "rows": limit,
            }
            _, data = self._http_get("works", params)
            message = data.get("message", {}) if isinstance(data, dict) else {}
            items = message.get("items", []) if isinstance(message, dict) else []

            for item in items:
                rec = self._parse_crossref_item(item)
                if rec:
                    records.append(rec)
        except Exception as exc:
            coverage_notes.append(f"Crossref search partially failed: {exc}")

        if not records and not coverage_notes:
            coverage_notes.append(f"No Crossref records matched query '{query.query_text}'")

        return ConnectorResult(
            source_id=self.SOURCE_ID,
            records=records,
            total_available=len(records),
            coverage_notes=coverage_notes,
            error=coverage_notes[0] if (not records and coverage_notes) else None,
        )

    def fetch_record(self, external_id: str) -> SourceRecord | None:
        """Fetches a work by DOI."""
        clean_doi = external_id.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
        try:
            _, data = self._http_get(f"works/{urllib.parse.quote(clean_doi, safe='')}", {})
            if isinstance(data, dict) and "message" in data:
                return self._parse_crossref_item(data["message"])
        except Exception as exc:
            logger.debug("Failed fetching Crossref record '%s': %s", external_id, exc)

        return None

    def _parse_crossref_item(self, item: dict[str, Any]) -> SourceRecord | None:
        raw_doi = item.get("DOI")
        if not raw_doi:
            return None

        normalized_doi = raw_doi.strip().lower()
        canonical_url = f"https://doi.org/{normalized_doi}"

        titles = item.get("title", [])
        title = titles[0] if titles and isinstance(titles, list) else "Untitled Publication"

        # Publication year
        published = item.get("published") or item.get("published-print") or item.get("created") or {}
        date_parts = published.get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        relationships: list[SourceRelationship] = []

        # Authors
        authors = item.get("author", [])
        for auth in authors[:5]:
            family = auth.get("family", "").strip()
            given = auth.get("given", "").strip()
            name = f"{given} {family}".strip() or family
            if name:
                person_id = f"crossref:{name.lower().replace(' ', '_')}"
                relationships.append(
                    SourceRelationship(
                        relation_type="AUTHORED",
                        source_entity_id=person_id,
                        target_entity_id=self.namespace_id(normalized_doi),
                        evidence_field="author",
                        confidence="EXACT",
                        provenance_url=canonical_url,
                    )
                )

                # Affiliations
                affs = auth.get("affiliation", [])
                for aff in affs[:2]:
                    aff_name = aff.get("name", "").strip()
                    if aff_name:
                        relationships.append(
                            SourceRelationship(
                                relation_type="AFFILIATED_WITH",
                                source_entity_id=person_id,
                                target_entity_id=f"org:crossref:{aff_name.lower().replace(' ', '_')[:40]}",
                                evidence_field="author.affiliation",
                                confidence="SUPPORTED",
                                provenance_url=canonical_url,
                            )
                        )

        # Funders
        funders = item.get("funder", [])
        for funder in funders[:3]:
            fname = funder.get("name", "").strip()
            if fname:
                relationships.append(
                    SourceRelationship(
                        relation_type="FUNDED_BY",
                        source_entity_id=self.namespace_id(normalized_doi),
                        target_entity_id=f"org:crossref:{fname.lower().replace(' ', '_')[:40]}",
                        evidence_field="funder.name",
                        confidence="SUPPORTED",
                        provenance_url=canonical_url,
                    )
                )

        # References
        references = item.get("reference", [])
        for ref in references[:5]:
            ref_doi = ref.get("DOI")
            if ref_doi:
                clean_ref_doi = ref_doi.strip().lower()
                relationships.append(
                    SourceRelationship(
                        relation_type="CITES",
                        source_entity_id=self.namespace_id(normalized_doi),
                        target_entity_id=f"crossref:{clean_ref_doi}",
                        evidence_field="reference.DOI",
                        confidence="SUPPORTED",
                        provenance_url=canonical_url,
                    )
                )

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type="Paper",
            external_id=normalized_doi,
            canonical_url=canonical_url,
            data={
                "title": title,
                "publication_year": year,
                "doi": normalized_doi,
                "publisher": item.get("publisher"),
            },
            relationships=relationships,
        )
        rec.compute_hash(json.dumps(item, sort_keys=True))
        return rec
