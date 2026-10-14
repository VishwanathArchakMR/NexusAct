"""FalkorDB client connection lifecycle, execution, and scenario isolation management."""

import logging
from typing import Any, Dict, List, Optional

from falkordb import FalkorDB
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
)
from redis.exceptions import (
    TimeoutError as RedisTimeoutError,
)

from backend.app.core.config import settings
from backend.app.core.errors import GraphConnectionError, GraphQueryError

logger = logging.getLogger("nexusact.graph.client")

# Protected production graph names that must never be deleted by disposable tests or scenario cleanup
PROTECTED_GRAPHS = frozenset(
    [
        "nexusact_main",
        "gaf_main",
        settings.FALKORDB_PRIMARY_GRAPH,
    ]
)


class FalkorDBClient:
    """Manages connections, queries, and graph lifecycles with FalkorDB."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        primary_graph: Optional[str] = None,
    ):
        self.host = host or settings.FALKORDB_HOST
        self.port = port or settings.FALKORDB_PORT
        self.password = password if password is not None else settings.FALKORDB_PASSWORD
        self.primary_graph_name = primary_graph or settings.FALKORDB_PRIMARY_GRAPH
        self._db: Optional[FalkorDB] = None

    def connect(self) -> FalkorDB:
        """Establishes or returns the existing FalkorDB connection."""
        if self._db is None:
            try:
                self._db = FalkorDB(
                    host=self.host,
                    port=self.port,
                    password=self.password if self.password else None,
                )
                # Verify basic socket ping
                self._db.connection.ping()
                logger.info("Connected to FalkorDB at %s:%d", self.host, self.port)
            except (RedisConnectionError, RedisTimeoutError, Exception) as exc:
                self._db = None
                logger.error("Failed connecting to FalkorDB at %s:%d: %s", self.host, self.port, exc)
                raise GraphConnectionError(
                    f"Unable to connect to FalkorDB at {self.host}:{self.port}: {str(exc)}",
                    details={"host": self.host, "port": self.port},
                ) from exc
        return self._db

    def ping(self) -> bool:
        """Checks if the FalkorDB service is reachable and responsive."""
        try:
            db = self.connect()
            return bool(db.connection.ping())
        except Exception:
            return False

    def select_graph(self, graph_name: Optional[str] = None):
        """Returns the requested graph instance or the default primary graph."""
        name = graph_name or self.primary_graph_name
        db = self.connect()
        return db.select_graph(name)

    def query(
        self,
        query_str: str,
        params: Optional[Dict[str, Any]] = None,
        graph_name: Optional[str] = None,
    ) -> List[Any]:
        """Executes a Cypher query on the designated graph with error handling."""
        target_name = graph_name or self.primary_graph_name
        try:
            g = self.select_graph(target_name)
            res = g.query(query_str, params=params)
            return res.result_set or []
        except Exception as exc:
            logger.error("Graph query error on [%s]: %s | Query: %s", target_name, exc, query_str)
            raise GraphQueryError(
                f"Query execution failed on graph '{target_name}': {str(exc)}",
                details={"graph": target_name, "query": query_str, "error": str(exc)},
            ) from exc

    def copy_graph(self, source_name: str, target_name: str) -> bool:
        """Copies an existing graph to an isolated destination graph via GRAPH.COPY."""
        if not source_name or not target_name:
            raise ValueError("source_name and target_name are required.")
        if target_name in PROTECTED_GRAPHS:
            raise ValueError(f"Target graph '{target_name}' is a protected graph name and cannot be overwritten.")

        db = self.connect()
        try:
            res = db.connection.execute_command("GRAPH.COPY", source_name, target_name)
            logger.info("Copied graph '%s' -> '%s' (Result: %s)", source_name, target_name, res)
            return True
        except Exception as exc:
            logger.error("GRAPH.COPY failed from '%s' to '%s': %s", source_name, target_name, exc)
            raise GraphQueryError(
                f"Failed to copy graph '{source_name}' to '{target_name}': {str(exc)}",
                details={"source": source_name, "target": target_name},
            ) from exc

    def delete_graph(self, graph_name: str, force: bool = False) -> bool:
        """Safely deletes a graph. Explicitly protects primary production graphs."""
        if graph_name in PROTECTED_GRAPHS and not force:
            raise ValueError(f"Safety violation: Cannot delete protected primary graph '{graph_name}'!")
        db = self.connect()
        try:
            g = db.select_graph(graph_name)
            g.delete()
            logger.info("Deleted graph '%s'", graph_name)
            return True
        except Exception as exc:
            logger.warning("Error deleting graph '%s': %s", graph_name, exc)
            return False

    def list_graphs(self) -> List[str]:
        """Returns list of active graphs in FalkorDB."""
        db = self.connect()
        try:
            raw = db.connection.execute_command("GRAPH.LIST")
            if isinstance(raw, list):
                return [item.decode("utf-8") if isinstance(item, bytes) else str(item) for item in raw]
            return []
        except Exception as exc:
            logger.error("Failed to list graphs: %s", exc)
            return []

    def get_graph_diagnostics(self, graph_name: Optional[str] = None) -> Dict[str, Any]:
        """Gathers counts and status for the specified graph."""
        name = graph_name or self.primary_graph_name
        is_connected = self.ping()
        if not is_connected:
            return {
                "graph_name": name,
                "connected": False,
                "status": "UNAVAILABLE",
                "node_count": 0,
                "edge_count": 0,
            }

        try:
            node_res = self.query("MATCH (n) RETURN count(n) AS cnt", graph_name=name)
            node_count = node_res[0][0] if node_res and len(node_res) > 0 else 0

            edge_res = self.query("MATCH ()-[r]->() RETURN count(r) AS cnt", graph_name=name)
            edge_count = edge_res[0][0] if edge_res and len(edge_res) > 0 else 0

            return {
                "graph_name": name,
                "connected": True,
                "status": "HEALTHY",
                "node_count": node_count,
                "edge_count": edge_count,
            }
        except Exception as exc:
            return {
                "graph_name": name,
                "connected": True,
                "status": "DEGRADED",
                "error": str(exc),
                "node_count": 0,
                "edge_count": 0,
            }

    def close(self):
        """Closes the underlying connection."""
        if self._db is not None:
            try:
                self._db.connection.close()
            except Exception:
                pass
            self._db = None
            logger.info("Closed FalkorDB connection.")


# Default singleton graph client instance
graph_client = FalkorDBClient()
