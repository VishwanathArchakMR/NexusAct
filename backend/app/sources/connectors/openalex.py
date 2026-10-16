"""OpenAlex public research and citation graph connector."""

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

logger = logging.getLogger("nexusact.sources.openalex")


class OpenAlexConnector(SourceConnector):
    """Read-only connector for the OpenAlex scholarly metadata and citation API."""

    SOURCE_ID: ClassVar[str] = "openalex"
    DISPLAY_NAME: ClassVar[str] = "OpenAlex Scholarly Graph"
    ENTITY_TYPES: ClassVar[list[str]] = ["Paper", "Person", "Organization", "Topic"]
    RELATIONSHIP_TYPES: ClassVar[list[str]] = ["AUTHORED", "AFFILIATED_WITH", "CITES", "HAS_TOPIC"]
    ATTRIBUTION: ClassVar[str] = "OpenAlex (https://openalex.org) under CC0 License"
    REQUIRES_AUTH: ClassVar[bool] = False
    MAX_RESULTS_PER_QUERY: ClassVar[int] = 10
    REQUEST_TIMEOUT_S: ClassVar[float] = 10.0

    API_BASE: ClassVar[str] = "https://api.openalex.org/"

    def _http_get(self, path: str, params: dict[str, Any], timeout: float | None = None) -> tuple[int, Any]:
        """Performs a bounded GET request to the fixed OpenAlex API base."""
        self._rate_limit()
        # OpenAlex polite pool via User-Agent mailto header
        params["mailto"] = "nexusact-research@example.org"
        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_BASE}{path}?{query_string}" if query_string else f"{self.API_BASE}{path}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NexusAct-GAF/1.0 (mailto:nexusact-research@example.org; Open-Source Evidence Engine)",
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
            logger.warning("OpenAlex API request failed for %s: %s", path, exc)
            raise

    def health_check(self) -> tuple[bool, str]:
        """Probes OpenAlex works endpoint with per-page=1 and fast timeout."""
        try:
            status, data = self._http_get("works", {"per-page": 1}, timeout=3.0)
            if status == 200 and isinstance(data, dict) and "results" in data:
                return True, "OpenAlex API reachable"
            return False, f"Unexpected response code: {status}"
        except Exception as exc:
            return False, f"OpenAlex API unreachable: {exc}"

    def search(self, query: ConnectorQuery) -> ConnectorResult:
        """Searches scholarly works and resolves authors, institutions, and topics."""
        limit = min(query.max_results, self.MAX_RESULTS_PER_QUERY)
        records: list[SourceRecord] = []
        coverage_notes: list[str] = []

        try:
            params = {
                "search": query.query_text,
                "per-page": limit,
                "select": "id,doi,title,publication_year,cited_by_count,authorships,topics,referenced_works",
            }
            _, data = self._http_get("works", params)
            results = data.get("results", []) if isinstance(data, dict) else []

            for item in results:
                rec = self._parse_work_item(item)
                if rec:
                    records.append(rec)
        except Exception as exc:
            coverage_notes.append(f"OpenAlex works search failed: {exc}")

        if not records and not coverage_notes:
            coverage_notes.append(f"No OpenAlex publications found for query '{query.query_text}'")

        return ConnectorResult(
            source_id=self.SOURCE_ID,
            records=records,
            total_available=len(records),
            coverage_notes=coverage_notes,
            error=coverage_notes[0] if (not records and coverage_notes) else None,
        )

    def fetch_record(self, external_id: str) -> SourceRecord | None:
        """Fetches a specific work by OpenAlex ID or DOI."""
        try:
            clean_id = external_id.strip()
            # If DOI, format with https://doi.org/...
            if clean_id.startswith("10."):
                path = f"works/https://doi.org/{clean_id}"
            elif clean_id.startswith("W"):
                path = f"works/{clean_id}"
            else:
                path = f"works/{urllib.parse.quote(clean_id, safe='')}"

            _, data = self._http_get(path, {})
            if isinstance(data, dict) and "id" in data:
                return self._parse_work_item(data)
        except Exception as exc:
            logger.debug("Failed fetching OpenAlex record '%s': %s", external_id, exc)

        return None

    def _parse_work_item(self, item: dict[str, Any]) -> SourceRecord | None:
        raw_id = item.get("id")
        if not raw_id:
            return None

        # Clean external ID (e.g. W2741809807)
        openalex_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
        doi = item.get("doi")
        normalized_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "") if doi else None
        primary_id = normalized_doi or openalex_id

        canonical_url = doi or raw_id
        title = item.get("title") or "Untitled Publication"
        year = item.get("publication_year")
        citations = item.get("cited_by_count", 0)

        relationships: list[SourceRelationship] = []

        # Authors and Affiliations
        authorships = item.get("authorships") or []
        for auth_entry in authorships[:5]:  # bound to top 5 authors
            author = auth_entry.get("author") or {}
            raw_author_id = author.get("id")
            author_id = str(raw_author_id).split("/")[-1] if raw_author_id else ""
            author_name = author.get("display_name", "")
            if author_id and author_name:
                person_node_id = f"openalex:{author_id}"
                # Person -> AUTHORED -> Paper
                relationships.append(
                    SourceRelationship(
                        relation_type="AUTHORED",
                        source_entity_id=person_node_id,
                        target_entity_id=self.namespace_id(primary_id),
                        evidence_field="authorships.author",
                        confidence="EXACT",
                        provenance_url=canonical_url,
                    )
                )

                # Affiliations: Person -> AFFILIATED_WITH -> Organization
                institutions = auth_entry.get("institutions") or []
                for inst in institutions[:2]:
                    raw_inst_id = inst.get("id")
                    inst_id = str(raw_inst_id).split("/")[-1] if raw_inst_id else ""
                    if inst_id:
                        relationships.append(
                            SourceRelationship(
                                relation_type="AFFILIATED_WITH",
                                source_entity_id=person_node_id,
                                target_entity_id=f"openalex:{inst_id}",
                                evidence_field="authorships.institutions",
                                confidence="SUPPORTED",
                                provenance_url=canonical_url,
                            )
                        )

        # Topics
        topics = item.get("topics") or []
        for topic in topics[:3]:
            t_name = topic.get("display_name")
            if t_name:
                relationships.append(
                    SourceRelationship(
                        relation_type="HAS_TOPIC",
                        source_entity_id=self.namespace_id(primary_id),
                        target_entity_id=f"topic:{t_name.lower().replace(' ', '-')}",
                        evidence_field="topics.display_name",
                        confidence="SUPPORTED",
                        provenance_url=canonical_url,
                    )
                )

        # Citations (referenced_works)
        referenced_works = item.get("referenced_works") or []
        for ref_id in referenced_works[:5]:
            if not ref_id:
                continue
            clean_ref = str(ref_id).split("/")[-1] if "/" in str(ref_id) else str(ref_id)
            relationships.append(
                SourceRelationship(
                    relation_type="CITES",
                    source_entity_id=self.namespace_id(primary_id),
                    target_entity_id=f"openalex:{clean_ref}",
                    evidence_field="referenced_works",
                    confidence="SUPPORTED",
                    provenance_url=canonical_url,
                )
            )

        rec = SourceRecord(
            source_id=self.SOURCE_ID,
            entity_type="Paper",
            external_id=primary_id,
            canonical_url=canonical_url,
            data={
                "title": title,
                "publication_year": year,
                "cited_by_count": citations,
                "doi": normalized_doi,
                "openalex_id": openalex_id,
            },
            relationships=relationships,
        )
        rec.compute_hash(json.dumps(item, sort_keys=True))
        return rec
