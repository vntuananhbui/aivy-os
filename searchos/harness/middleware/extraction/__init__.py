"""Compatibility facade for canonical research extraction middleware."""

from ai.research.orchestration.middleware.extraction import (
    EvidenceExtractionMiddleware,
    EvidenceIntake,
    ExtractionMiddleware,
)

__all__ = ["EvidenceExtractionMiddleware", "EvidenceIntake", "ExtractionMiddleware"]
