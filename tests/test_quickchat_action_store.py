import asyncio

from backend.infrastructure.database import quickchat_sqlite
from backend.infrastructure.conversations.sqlite_stores import action_workflow_repository


def test_action_workflow_round_trip_and_single_resume_lease(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quickchat_sqlite, "DB_PATH", tmp_path / "quickchat.db")

    async def scenario() -> None:
        created = await action_workflow_repository.upsert(
            "thread-1",
            agent_type="teams_meeting_action",
            status="awaiting_approval",
            thinking=False,
            effort="medium",
            graph_build_key="2026-08-19",
            interrupt_id="interrupt-1",
        )
        assert created.status == "awaiting_approval"
        assert created.interrupt_id == "interrupt-1"

        first, second = await asyncio.gather(
            action_workflow_repository.acquire_resume_lease(
                "thread-1", "interrupt-1", "request-a"
            ),
            action_workflow_repository.acquire_resume_lease(
                "thread-1", "interrupt-1", "request-b"
            ),
        )
        winners = [lease for lease in (first, second) if lease is not None]
        assert len(winners) == 1
        assert winners[0].status == "resuming"

        owner = winners[0].lease_owner
        assert owner is not None
        assert await action_workflow_repository.finish_resume(
            "thread-1", owner, status="completed"
        )
        final = await action_workflow_repository.get("thread-1")
        assert final is not None
        assert final.status == "completed"
        assert final.interrupt_id is None

    asyncio.run(scenario())


def test_action_workflow_delete(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quickchat_sqlite, "DB_PATH", tmp_path / "quickchat.db")

    async def scenario() -> None:
        await action_workflow_repository.upsert(
            "thread-delete",
            agent_type="teams_meeting_action",
            status="collecting",
            thinking=True,
            effort="high",
            graph_build_key="2026-08-19",
        )
        await action_workflow_repository.delete("thread-delete")
        assert await action_workflow_repository.get("thread-delete") is None

    asyncio.run(scenario())
