"""Compatibility facade for canonical evidence intake."""

from ai.research.orchestration.middleware.extraction.intake import (
    DeliveryMode,
    EvidenceIntake,
    EvidenceObservation,
    EvidenceSourceKind,
    EvidenceStore,
    InMemoryEvidenceStore,
    IntakeConfig,
    IntakeReceipt,
    IntakeSummary,
    WorkspaceEvidenceStore,
    replay_pending_summaries,
)

__all__ = [
    "DeliveryMode", "EvidenceIntake", "EvidenceObservation", "EvidenceSourceKind",
    "EvidenceStore", "InMemoryEvidenceStore", "IntakeConfig", "IntakeReceipt",
    "IntakeSummary", "WorkspaceEvidenceStore", "replay_pending_summaries",
]
