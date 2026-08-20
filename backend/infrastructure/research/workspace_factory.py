"""Backend composition factory for local filesystem research workspaces."""

from __future__ import annotations

from pathlib import Path

from ai.research.orchestration.workspace import ResearchWorkspacePort
from backend.infrastructure.research.workspace import WorkspaceManager


class FilesystemResearchWorkspaceFactory:
    def create_workspace(
        self, root: str | Path, session_id: str | None = None
    ) -> ResearchWorkspacePort:
        return WorkspaceManager(root, session_id)


__all__ = ["FilesystemResearchWorkspaceFactory"]
