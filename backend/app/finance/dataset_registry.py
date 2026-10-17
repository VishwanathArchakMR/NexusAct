"""Registry and lifecycle management for imported financial datasets."""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.core.config import settings
from backend.app.finance.models import FinancialDatasetMetadata
from backend.app.graph.client import FalkorDBClient, graph_client

logger = logging.getLogger("nexusact.finance.registry")

_PROTECTED_SYSTEM_GRAPHS = {
    "nexusact_main",
    "nexusact_public",
    "aletheia_os",
}


class FinancialDatasetRegistry:
    """Manages metadata, persistence, and graph lifecycle for financial datasets."""

    def __init__(self, persistence_path: Optional[Path] = None, client: Optional[FalkorDBClient] = None):
        self._lock = threading.Lock()
        self._client = client or graph_client
        self._datasets: Dict[str, FinancialDatasetMetadata] = {}
        self._active_dataset_id: Optional[str] = None
        self._persistence_file = (
            persistence_path
            or Path(getattr(settings, "NEXUSACT_REPOSITORY_PATH", ".")) / ".cache" / "nexusact_finance_datasets.json"
        )
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Loads registered datasets from persistent disk cache if present."""
        try:
            if self._persistence_file.exists():
                data = json.loads(self._persistence_file.read_text(encoding="utf-8"))
                for ds_dict in data.get("datasets", []):
                    try:
                        ds = FinancialDatasetMetadata(**ds_dict)
                        self._datasets[ds.dataset_id] = ds
                    except Exception as parse_err:
                        logger.warning("Could not deserialize dataset record: %s", parse_err)
                self._active_dataset_id = data.get("active_dataset_id")
                if not self._active_dataset_id and self._datasets:
                    self._active_dataset_id = next(iter(self._datasets.keys()))
        except Exception as e:
            logger.warning("Could not read financial datasets from %s: %s", self._persistence_file, e)

    def _save_to_disk(self) -> None:
        """Persists registered datasets to disk cache."""
        try:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "active_dataset_id": self._active_dataset_id,
                "datasets": [ds.model_dump() for ds in self._datasets.values()],
            }
            self._persistence_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not save financial datasets to disk: %s", e)

    def register_dataset(self, metadata: FinancialDatasetMetadata) -> None:
        """Registers a new validated dataset and sets it as the active dataset."""
        with self._lock:
            self._datasets[metadata.dataset_id] = metadata
            self._active_dataset_id = metadata.dataset_id
            self._save_to_disk()
            logger.info(
                "Registered financial dataset %s (%s) on graph %s",
                metadata.dataset_id,
                metadata.name,
                metadata.graph_name,
            )

    def get_dataset(self, dataset_id: str) -> Optional[FinancialDatasetMetadata]:
        """Retrieves metadata for a specific dataset."""
        with self._lock:
            return self._datasets.get(dataset_id)

    def get_active_dataset(self) -> Optional[FinancialDatasetMetadata]:
        """Returns the currently active financial dataset, or None if none registered."""
        with self._lock:
            if self._active_dataset_id and self._active_dataset_id in self._datasets:
                return self._datasets[self._active_dataset_id]
            if self._datasets:
                first_key = next(iter(self._datasets.keys()))
                self._active_dataset_id = first_key
                return self._datasets[first_key]
            return None

    def set_active_dataset(self, dataset_id: str) -> bool:
        """Sets the active financial dataset ID if valid."""
        with self._lock:
            if dataset_id in self._datasets:
                self._active_dataset_id = dataset_id
                self._save_to_disk()
                return True
            return False

    def list_datasets(self) -> List[FinancialDatasetMetadata]:
        """Lists all registered financial datasets ordered by creation time descending."""
        with self._lock:
            return sorted(
                list(self._datasets.values()),
                key=lambda d: d.created_at,
                reverse=True,
            )

    def delete_dataset(self, dataset_id: str) -> bool:
        """Deletes a dataset record and drops its isolated graph from FalkorDB."""
        with self._lock:
            if dataset_id not in self._datasets:
                return False

            ds = self._datasets[dataset_id]
            graph_to_drop = ds.graph_name

            # Guard against deleting system graphs
            if graph_to_drop in _PROTECTED_SYSTEM_GRAPHS or graph_to_drop.startswith("nexusact_"):
                logger.warning("Refusing to drop protected system graph: %s", graph_to_drop)
            else:
                try:
                    self._client.delete_graph(graph_to_drop)
                    logger.info("Successfully dropped FalkorDB graph: %s", graph_to_drop)
                except Exception as e:
                    logger.warning("Error dropping FalkorDB graph %s: %s", graph_to_drop, e)

            del self._datasets[dataset_id]
            if self._active_dataset_id == dataset_id:
                self._active_dataset_id = next(iter(self._datasets.keys())) if self._datasets else None

            self._save_to_disk()
            return True


# Global registry singleton
dataset_registry = FinancialDatasetRegistry()
financial_registry = dataset_registry
