"""Storage-neutral workspace contracts used by research orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from searchos.socm.state import SearchState


class ResearchWorkspacePort(Protocol):
    @property
    def path(self) -> Path: ...

    @property
    def session_id(self) -> str: ...

    @property
    def trajectory_path(self) -> Path: ...

    @property
    def conversation_path(self) -> Path: ...

    @property
    def state(self) -> SearchState: ...

    @property
    def extraction_pending_total(self) -> int: ...

    def create(self) -> Path: ...

    def save_state(self, state: SearchState) -> None: ...

    def load_state(self) -> SearchState: ...

    def atomic_update_state(
        self, updater: Callable[[SearchState], SearchState]
    ) -> SearchState: ...

    def report_extraction_pending(self, owner: Any, count: int) -> None: ...

    def write_output(self, filename: str, content: str) -> Path: ...

    def save_turn_snapshot(
        self,
        query: str,
        state: SearchState,
        metadata: dict[str, Any] | None = None,
    ) -> Path: ...


class ResearchWorkspaceFactory(Protocol):
    def create_workspace(
        self, root: str | Path, session_id: str | None = None
    ) -> ResearchWorkspacePort: ...


__all__ = ["ResearchWorkspaceFactory", "ResearchWorkspacePort"]
