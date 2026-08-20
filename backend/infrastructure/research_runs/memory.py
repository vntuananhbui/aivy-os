"""Process-local research run repository and migration compatibility view."""

from __future__ import annotations

from threading import RLock

from backend.application.research_runs.models import ResearchRun


class InMemoryResearchRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, ResearchRun] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> ResearchRun | None:
        with self._lock:
            return self._runs.get(session_id)

    def save(self, run: ResearchRun) -> None:
        with self._lock:
            self._runs[run.session_id] = run

    def claim_start(self, run: ResearchRun) -> bool:
        with self._lock:
            current = self._runs.get(run.session_id)
            if current is not None and current.status == "running":
                return False
            self._runs[run.session_id] = run
            return True

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._runs.pop(session_id, None)

    def list(self) -> list[ResearchRun]:
        with self._lock:
            return list(self._runs.values())
__all__ = ["InMemoryResearchRunRepository"]
