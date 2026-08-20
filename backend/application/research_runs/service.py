"""Application service for live research run lifecycle operations."""

from __future__ import annotations

from typing import Any

from backend.application.research_runs.models import ResearchRun
from backend.application.research_runs.repositories import ResearchRunRepository


class ResearchRunService:
    def __init__(self, repository: ResearchRunRepository) -> None:
        self._repository = repository

    def get(self, session_id: str) -> ResearchRun | None:
        return self._repository.get(session_id)

    def start(
        self,
        session_id: str,
        *,
        harness: Any,
        initial_state: Any,
        steer_queue: Any,
    ) -> ResearchRun:
        run = ResearchRun(
            session_id=session_id,
            status="running",
            harness=harness,
            initial_state=initial_state,
            steer_queue=steer_queue,
        )
        if not self._repository.claim_start(run):
            raise RuntimeError(f"Session {session_id} is already running")
        return run

    def attach_task(self, session_id: str, task: Any) -> ResearchRun:
        run = self._require(session_id)
        run.task = task
        self._repository.save(run)
        return run

    def complete(self, session_id: str, result: Any) -> ResearchRun:
        run = self._require(session_id)
        run.result = result
        run.error = None
        run.status = "completed"
        self._repository.save(run)
        return run

    def fail(self, session_id: str, error: str) -> ResearchRun:
        run = self._require(session_id)
        run.error = error
        run.status = "error"
        self._repository.save(run)
        return run

    def cancel(self, session_id: str) -> bool:
        run = self._repository.get(session_id)
        if run is None or run.status != "running":
            return False
        task = run.task
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def steer(self, session_id: str, message: str) -> bool:
        run = self._repository.get(session_id)
        if run is None or run.status != "running" or run.steer_queue is None:
            return False
        run.steer_queue.put_nowait(message)
        return True

    def list(self) -> list[ResearchRun]:
        return self._repository.list()

    def delete(self, session_id: str) -> None:
        self._repository.delete(session_id)

    def _require(self, session_id: str) -> ResearchRun:
        run = self._repository.get(session_id)
        if run is None:
            raise KeyError(f"Research run {session_id!r} not found")
        return run


__all__ = ["ResearchRunService"]
