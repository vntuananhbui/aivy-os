"""Composition factory for filesystem-backed research telemetry."""

from __future__ import annotations

from pathlib import Path

from ai.research.telemetry.ports import ConversationLoggerPort, TrajectoryLoggerPort
from backend.infrastructure.research.conversation_logger import ConversationLogger
from backend.infrastructure.research.trajectory_logger import TrajectoryLogger


class FilesystemResearchTelemetryFactory:
    def create_conversation_logger(
        self, path: str | Path
    ) -> ConversationLoggerPort:
        return ConversationLogger(path)

    def create_trajectory_logger(self, path: str | Path) -> TrajectoryLoggerPort:
        return TrajectoryLogger(path)


__all__ = ["FilesystemResearchTelemetryFactory"]
