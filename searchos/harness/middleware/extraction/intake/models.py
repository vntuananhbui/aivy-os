"""Compatibility facade for canonical evidence-intake models."""

from ai.research.orchestration.middleware.extraction.intake.models import (
    DeliveryMode,
    EvidenceObservation,
    EvidenceSourceKind,
    IntakeConfig,
    IntakeReceipt,
    IntakeSummary,
)

__all__ = [
    "DeliveryMode", "EvidenceObservation", "EvidenceSourceKind", "IntakeConfig",
    "IntakeReceipt", "IntakeSummary",
]
