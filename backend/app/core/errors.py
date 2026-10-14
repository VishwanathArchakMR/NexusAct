"""Application error classes and response models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized API error response format."""

    error: str = Field(..., description="Error classification or code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional context or diagnostics")
    request_id: Optional[str] = Field(default=None, description="Correlation or request identifier")


class NexusActError(Exception):
    """Base exception for NexusAct application errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GraphConnectionError(NexusActError):
    """Raised when the application cannot connect to FalkorDB."""

    pass


class GraphQueryError(NexusActError):
    """Raised when a graph query fails execution."""

    pass


class SchemaInitializationError(NexusActError):
    """Raised when schema initialization or index creation fails."""

    pass
