import asyncio

from backend.application.conversations.models import ConversationSummary
from backend.application.conversations.service import ConversationService


class MetadataRepository:
    def __init__(self):
        self.deleted = []

    async def list(self, *, limit=100):
        return [ConversationSummary("thread-1", "Hello", 1.0, 2.0)][:limit]

    async def delete(self, thread_id):
        self.deleted.append(thread_id)


class ThreadGateway:
    def __init__(self, messages=None):
        self.messages = messages
        self.deleted = []

    async def load_messages(self, thread_id):
        return self.messages

    async def pending_approval(self, thread_id):
        return {"interrupt_id": "approval-1"}

    async def delete(self, thread_id):
        self.deleted.append(thread_id)


def test_conversation_service_combines_messages_and_pending_approval() -> None:
    service = ConversationService(
        metadata=MetadataRepository(),
        threads=ThreadGateway(messages=[{"role": "user", "text": "Hello"}]),
    )

    detail = asyncio.run(service.get("thread-1"))

    assert detail is not None
    assert detail.thread_id == "thread-1"
    assert detail.messages[0]["text"] == "Hello"
    assert detail.pending_approval == {"interrupt_id": "approval-1"}


def test_conversation_service_returns_none_when_checkpoint_is_missing() -> None:
    service = ConversationService(
        metadata=MetadataRepository(),
        threads=ThreadGateway(messages=None),
    )

    assert asyncio.run(service.get("missing")) is None


def test_conversation_service_deletes_thread_state_then_metadata() -> None:
    metadata = MetadataRepository()
    threads = ThreadGateway()
    service = ConversationService(metadata=metadata, threads=threads)

    asyncio.run(service.delete("thread-1"))

    assert threads.deleted == ["thread-1"]
    assert metadata.deleted == ["thread-1"]
