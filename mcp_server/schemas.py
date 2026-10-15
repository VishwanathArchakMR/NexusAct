"""Typed schemas and contracts for NexusAct MCP tools."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

# Re-export core graph tool schemas for MCP consumers
from backend.app.graph.tools.centrality import PageRankInput, PageRankOutput
from backend.app.graph.tools.impact import TraceImpactInput, TraceImpactOutput
from backend.app.graph.tools.reviewers import WhoKnowsInput, WhoKnowsOutput
from backend.app.graph.tools.simulation import SimulateRemoveModuleInput, SimulationResult


class ToolClassification(str, Enum):
    """Safety classification for agent-invocable MCP tools."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


class GraphDiagnosticInput(BaseModel):
    """Input payload for the nexusact_diagnose_graph diagnostic tool."""

    graph_name: Optional[str] = Field(
        default=None,
        description="Target graph name to inspect (defaults to primary graph if omitted)",
        max_length=64,
    )
    include_labels: bool = Field(
        default=True,
        description="Whether to inspect distinct node labels in the graph",
    )


class GraphDiagnosticOutput(BaseModel):
    """Bounded, typed output from nexusact_diagnose_graph tool."""

    tool_version: str = Field(..., description="Semantic version of the diagnostic tool")
    graph_name: str = Field(..., description="Inspected graph name")
    connected: bool = Field(..., description="Whether FalkorDB connection succeeded")
    status: str = Field(..., description="HEALTHY, DEGRADED, or UNAVAILABLE")
    node_count: int = Field(..., description="Total nodes in the graph")
    edge_count: int = Field(..., description="Total edges in the graph")
    schema_version: str = Field(..., description="Installed schema version")
    labels: List[str] = Field(default_factory=list, description="Discovered node labels")
    diagnostics_message: str = Field(..., description="Human-readable status summary")


__all__ = [
    "ToolClassification",
    "GraphDiagnosticInput",
    "GraphDiagnosticOutput",
    "TraceImpactInput",
    "TraceImpactOutput",
    "WhoKnowsInput",
    "WhoKnowsOutput",
    "PageRankInput",
    "PageRankOutput",
    "SimulateRemoveModuleInput",
    "SimulationResult",
]
