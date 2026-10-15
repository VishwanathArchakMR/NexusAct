"""Evidence and claim verification package (Phase 2 foundation)."""

from backend.app.evidence.verifier import (
    PathVerificationResult,
    PathVerifier,
    VerificationCheck,
    VerificationStatus,
    path_verifier,
)

__all__ = [
    "PathVerifier",
    "path_verifier",
    "VerificationStatus",
    "PathVerificationResult",
    "VerificationCheck",
]
