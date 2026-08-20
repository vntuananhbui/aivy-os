"""Telemetry ports owned by the research AI application layer.

Concrete storage (filesystem, database, object storage) belongs to backend
infrastructure and is supplied through ``ResearchTelemetryFactory``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ai.research.telemetry.models import ConversationMessage, StateDelta


class ConversationLoggerPort(Protocol):
    def hydrate(self) -> None: ...

    def log(self, message: ConversationMessage) -> None: ...

    def register_sub_agent(
        self,
        agent_name: str,
        parent: str,
        task: str,
        system_prompt: str = "",
        agent_type: str = "",
    ) -> None: ...


class TrajectoryLoggerPort(Protocol):
    _step_count: int

    def add_listener(self, cb: Callable[[dict], None]) -> None: ...

    def _append_raw(self, record: dict) -> None: ...

    @staticmethod
    def _compute_step_value(delta: StateDelta) -> float: ...

    @property
    def step_count(self) -> int: ...

    @property
    def tool_counts(self) -> dict[str, int]: ...


class ResearchTelemetryFactory(Protocol):
    def create_conversation_logger(
        self, path: str | Path
    ) -> ConversationLoggerPort: ...

    def create_trajectory_logger(self, path: str | Path) -> TrajectoryLoggerPort: ...


class InMemoryConversationLogger:
    """Safe non-persistent fallback for library callers without a backend."""

    def __init__(self) -> None:
        self.messages: list[ConversationMessage] = []

    def hydrate(self) -> None:
        return None

    def log(self, message: ConversationMessage) -> None:
        self.messages.append(message)

    def register_sub_agent(
        self,
        agent_name: str,
        parent: str,
        task: str,
        system_prompt: str = "",
        agent_type: str = "",
    ) -> None:
        return None


class InMemoryTrajectoryLogger:
    """Non-persistent trajectory sink that preserves listeners and counters."""

    def __init__(self) -> None:
        self._step_count = 0
        self._tool_counts: dict[str, int] = {}
        self._listeners: list[Callable[[dict], None]] = []

    def add_listener(self, cb: Callable[[dict], None]) -> None:
        self._listeners.append(cb)

    def _append_raw(self, record: dict) -> None:
        if record.get("type") == "step":
            action = record.get("action")
            action_name = (
                str(action.get("name") or "")
                if isinstance(action, dict)
                else str(action or "")
            )
            if action_name:
                self._tool_counts[action_name] = self._tool_counts.get(action_name, 0) + 1
        for listener in self._listeners:
            try:
                listener(record)
            except Exception:
                pass

    @staticmethod
    def _compute_step_value(delta: StateDelta) -> float:
        value = delta.coverage_gain * 2.0
        value += delta.new_evidence_count * 0.3
        value += len(delta.frontier_resolved) * 0.5
        value += delta.conflicts_resolved * 0.4
        return round(value, 4)

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def tool_counts(self) -> dict[str, int]:
        return dict(self._tool_counts)


class InMemoryResearchTelemetryFactory:
    """Default factory for embedding the AI package without backend storage."""

    def create_conversation_logger(
        self, path: str | Path
    ) -> ConversationLoggerPort:
        return InMemoryConversationLogger()

    def create_trajectory_logger(self, path: str | Path) -> TrajectoryLoggerPort:
        return InMemoryTrajectoryLogger()


__all__ = [
    "ConversationLoggerPort",
    "InMemoryResearchTelemetryFactory",
    "ResearchTelemetryFactory",
    "TrajectoryLoggerPort",
]
