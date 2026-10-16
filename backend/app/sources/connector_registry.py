"""
Universal Source Connector Registry — GraphAction Fabric (GAF) Phase 7.

Provides a typed, extensible registry of read-only public-data connectors.
Each connector declares its identity, supported entity types, relationships,
authentication requirements, rate limits, and health status.

Security contract:
  - All outbound API bases are fixed constants in each connector class.
  - No user-controlled URL is ever used as an API destination.
  - Request construction uses safe parameter encoding only.
  - Response sizes are bounded; pagination is capped.
  - External text is treated as untrusted data, never as instructions.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Provenance & Evidence
# ---------------------------------------------------------------------------


@dataclass
class SourceRecord:
    """Represents a single fetched record with provenance metadata."""

    source_id: str
    """Stable identifier of the connector that produced this record."""

    entity_type: str
    """Canonical entity type: 'Model', 'Dataset', 'Paper', 'Person', etc."""

    external_id: str
    """Stable external identifier (e.g. 'meta-llama/Llama-3-8B', 'W1234567')."""

    canonical_url: str
    """Authoritative URL for this record at the source."""

    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """ISO-8601 UTC timestamp of retrieval."""

    raw_hash: str = ""
    """SHA-256 hex digest of the raw response payload for integrity tracking."""

    data: dict[str, Any] = field(default_factory=dict)
    """Normalised, sanitised fields extracted from the source record."""

    relationships: list["SourceRelationship"] = field(default_factory=list)
    """Typed relationships supported by the source record."""

    coverage_notes: list[str] = field(default_factory=list)
    """Explicit statements about what information is absent or uncertain."""

    def compute_hash(self, raw: str) -> None:
        self.raw_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class SourceRelationship:
    """A typed relationship supported by a source record."""

    relation_type: str
    """e.g. 'AUTHORED', 'CITES', 'USES_DATASET', 'AFFILIATED_WITH'."""

    source_entity_id: str
    """Namespaced ID of the originating entity."""

    target_entity_id: str
    """Namespaced ID of the target entity."""

    evidence_field: str
    """Field or section of the source record that supports this claim."""

    confidence: str = "SUPPORTED"
    """EXACT, HIGH, SUPPORTED, UNCERTAIN, or UNKNOWN."""

    provenance_url: str = ""
    """URL pointing to the source statement."""


@dataclass
class ConnectorQuery:
    """A bounded query request sent to a connector."""

    query_text: str
    """Free-text search term or identifier."""

    entity_types: list[str] = field(default_factory=list)
    """Limit results to these entity types. Empty = all supported."""

    max_results: int = 10
    """Hard upper limit on returned records (connector may apply tighter cap)."""

    filters: dict[str, Any] = field(default_factory=dict)
    """Source-specific filter parameters."""


@dataclass
class ConnectorResult:
    """Bounded result set returned by a connector."""

    source_id: str
    records: list[SourceRecord]
    total_available: int = 0
    """Best estimate of total matching records at source (-1 = unknown)."""
    is_truncated: bool = False
    coverage_notes: list[str] = field(default_factory=list)
    error: str | None = None
    """Set when the connector encountered a partial or full failure."""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Connector Protocol
# ---------------------------------------------------------------------------


class SourceConnector(ABC):
    """Abstract base for all public-data source connectors.

    Subclasses must:
      - Set class-level SOURCE_ID, DISPLAY_NAME, ENTITY_TYPES, RELATIONSHIP_TYPES.
      - Fix API base URLs as class constants — never accept user-supplied URLs.
      - Implement search() and fetch_record() with bounded pagination.
      - Implement health_check() to verify the source is reachable.
    """

    SOURCE_ID: ClassVar[str]
    DISPLAY_NAME: ClassVar[str]
    ENTITY_TYPES: ClassVar[list[str]]
    RELATIONSHIP_TYPES: ClassVar[list[str]]
    ATTRIBUTION: ClassVar[str]
    REQUIRES_AUTH: ClassVar[bool] = False
    MAX_RESULTS_PER_QUERY: ClassVar[int] = 20
    REQUEST_TIMEOUT_S: ClassVar[float] = 15.0
    MAX_RESPONSE_BYTES: ClassVar[int] = 512 * 1024  # 512 KB

    def __init__(self) -> None:
        self._last_request_ts: float = 0.0
        self._min_interval_s: float = 1.0  # conservative default

    def _rate_limit(self) -> None:
        """Enforces minimum inter-request interval."""
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self._min_interval_s:
            time.sleep(self._min_interval_s - elapsed)
        self._last_request_ts = time.monotonic()

    @abstractmethod
    def search(self, query: ConnectorQuery) -> ConnectorResult:
        """Returns bounded search results for the query."""

    @abstractmethod
    def fetch_record(self, external_id: str) -> SourceRecord | None:
        """Fetches a single record by its stable external identifier."""

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        """Returns (is_healthy, message)."""

    def namespace_id(self, external_id: str) -> str:
        """Returns a namespaced graph node ID: '<source_id>:<external_id>'."""
        return f"{self.SOURCE_ID}:{external_id}"


# ---------------------------------------------------------------------------
# Connector Registry
# ---------------------------------------------------------------------------


class ConnectorRegistry:
    """Singleton registry of approved source connectors.

    Connectors are registered by source ID.  The discovery planner selects
    connectors from this registry only — arbitrary URLs are never used.
    """

    _connectors: dict[str, SourceConnector] = {}

    @classmethod
    def init_defaults(cls) -> None:
        """Initializes and registers the default approved source connectors."""
        if not cls._connectors:
            from backend.app.sources.connectors.crossref import CrossrefConnector
            from backend.app.sources.connectors.huggingface import HuggingFaceConnector
            from backend.app.sources.connectors.openalex import OpenAlexConnector
            from backend.app.sources.connectors.wikidata import WikidataConnector

            cls.register(HuggingFaceConnector())
            cls.register(OpenAlexConnector())
            cls.register(CrossrefConnector())
            cls.register(WikidataConnector())

    @classmethod
    def register(cls, connector: SourceConnector) -> None:
        cls._connectors[connector.SOURCE_ID] = connector

    @classmethod
    def get(cls, source_id: str) -> SourceConnector | None:
        cls.init_defaults()
        return cls._connectors.get(source_id)

    @classmethod
    def all(cls) -> list[SourceConnector]:
        cls.init_defaults()
        return list(cls._connectors.values())

    @classmethod
    def all_source_ids(cls) -> list[str]:
        cls.init_defaults()
        return list(cls._connectors.keys())

    _cached_health: dict[str, dict[str, Any]] | None = None
    _cached_health_ts: float = 0.0
    _HEALTH_CACHE_TTL_S: float = 60.0

    @classmethod
    def health_status(cls, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """Returns health status for all registered connectors, with bounded TTL caching."""
        cls.init_defaults()
        now = time.monotonic()
        if (
            not force_refresh
            and cls._cached_health is not None
            and (now - cls._cached_health_ts) < cls._HEALTH_CACHE_TTL_S
        ):
            return cls._cached_health

        status: dict[str, dict[str, Any]] = {}
        for sid, conn in cls._connectors.items():
            try:
                is_healthy, msg = conn.health_check()
                status[sid] = {
                    "source_id": sid,
                    "display_name": conn.DISPLAY_NAME,
                    "healthy": is_healthy,
                    "message": msg,
                    "entity_types": conn.ENTITY_TYPES,
                    "requires_auth": conn.REQUIRES_AUTH,
                }
            except Exception as exc:
                status[sid] = {
                    "source_id": sid,
                    "display_name": conn.DISPLAY_NAME,
                    "healthy": False,
                    "message": f"Health check raised: {exc}",
                    "entity_types": conn.ENTITY_TYPES,
                    "requires_auth": conn.REQUIRES_AUTH,
                }
        cls._cached_health = status
        cls._cached_health_ts = now
        return status

    @classmethod
    def select_for_entity_types(cls, entity_types: list[str]) -> list[SourceConnector]:
        """Returns connectors that support at least one of the requested entity types."""
        cls.init_defaults()
        selected = []
        for conn in cls._connectors.values():
            if not entity_types or any(et in conn.ENTITY_TYPES for et in entity_types):
                selected.append(conn)
        return selected
