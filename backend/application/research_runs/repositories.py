"""Persistence port for research run lifecycle state."""

from __future__ import annotations

from typing import Protocol

from backend.application.research_runs.models import ResearchRun


class ResearchRunRepository(Protocol):
    def get(self, session_id: str) -> ResearchRun | None: ...

    def save(self, run: ResearchRun) -> None: ...

    def claim_start(self, run: ResearchRun) -> bool: ...

    def delete(self, session_id: str) -> None: ...

    def list(self) -> list[ResearchRun]: ...


__all__ = ["ResearchRunRepository"]
