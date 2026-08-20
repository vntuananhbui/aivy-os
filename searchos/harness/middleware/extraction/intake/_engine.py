"""Compatibility facade for the canonical evidence-intake engine."""

from ai.research.orchestration.middleware.extraction.intake._engine import (
    EvidenceIntake,
    _anchored_excerpt,
    _extract_context,
    _fold_digits,
    _provenance_fields,
    _ungrounded_number,
)

__all__ = ["EvidenceIntake"]
