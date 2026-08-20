"""Compatibility facade for canonical evidence-intake stores."""

from ai.research.orchestration.middleware.extraction.intake.store import (
    EvidenceStore,
    InMemoryEvidenceStore,
    WorkspaceEvidenceStore,
)

__all__ = ["EvidenceStore", "InMemoryEvidenceStore", "WorkspaceEvidenceStore"]
