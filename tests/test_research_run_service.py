from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.application.research_runs.service import ResearchRunService
from backend.infrastructure.research_runs.memory import InMemoryResearchRunRepository


def _start(service: ResearchRunService, session_id: str = "run-1"):
    return service.start(
        session_id,
        harness=object(),
        initial_state={"query": "test"},
        steer_queue=asyncio.Queue(),
    )


def test_run_lifecycle_is_persisted_through_repository_port() -> None:
    repository = InMemoryResearchRunRepository()
    service = ResearchRunService(repository)

    _start(service)
    assert repository.get("run-1").status == "running"

    result = object()
    service.complete("run-1", result)

    assert repository.get("run-1").status == "completed"
    assert repository.get("run-1").result is result

    service.delete("run-1")
    assert service.get("run-1") is None


def test_claim_start_allows_only_one_concurrent_running_owner() -> None:
    service = ResearchRunService(InMemoryResearchRunRepository())

    def attempt() -> bool:
        try:
            _start(service, "same-run")
            return True
        except RuntimeError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        accepted = list(executor.map(lambda _: attempt(), range(16)))

    assert sum(accepted) == 1


def test_steer_and_cancel_are_guarded_by_running_status() -> None:
    class PendingTask:
        cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self.cancelled = True

    service = ResearchRunService(InMemoryResearchRunRepository())
    run = _start(service)
    task = PendingTask()
    service.attach_task(run.session_id, task)

    assert service.steer(run.session_id, "follow up") is True
    assert run.steer_queue.get_nowait() == "follow up"
    assert service.cancel(run.session_id) is True
    assert task.cancelled is True

    service.fail(run.session_id, "stopped")
    assert service.steer(run.session_id, "late") is False
    assert service.cancel(run.session_id) is False
