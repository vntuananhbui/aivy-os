"""Conversation use cases shared by HTTP and future non-HTTP callers."""

from __future__ import annotations

from backend.application.conversations.models import ConversationDetail, ConversationSummary
from backend.application.conversations.repositories import (
    ConversationMetadataRepository,
    ConversationThreadGateway,
)


class ConversationService:
    def __init__(
        self,
        *,
        metadata: ConversationMetadataRepository,
        threads: ConversationThreadGateway,
    ) -> None:
        self._metadata = metadata
        self._threads = threads

    async def list(self, *, limit: int = 100) -> list[ConversationSummary]:
        return await self._metadata.list(limit=limit)

    async def get(self, thread_id: str) -> ConversationDetail | None:
        messages = await self._threads.load_messages(thread_id)
        if messages is None:
            return None
        return ConversationDetail(
            thread_id=thread_id,
            messages=messages,
            pending_approval=await self._threads.pending_approval(thread_id),
        )

    async def delete(self, thread_id: str) -> None:
        await self._threads.delete(thread_id)
        await self._metadata.delete(thread_id)
