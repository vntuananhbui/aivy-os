import asyncio

from backend.infrastructure.conversations.sqlite_stores import (
    SQLiteConversationMetadataRepository,
)
from backend.infrastructure.database import quickchat_sqlite


def test_sqlite_conversation_repository_preserves_first_title(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(quickchat_sqlite, "DB_PATH", tmp_path / "quickchat.db")
    repository = SQLiteConversationMetadataRepository()

    async def scenario():
        await repository.touch("thread-1", "  First   message  ")
        await repository.touch("thread-1", "Second message must not replace title")
        return await repository.list(limit=10)

    conversations = asyncio.run(scenario())

    assert len(conversations) == 1
    assert conversations[0].thread_id == "thread-1"
    assert conversations[0].title == "First message"
