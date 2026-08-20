"""Adapters over the existing QuickChat SQLite stores and ChatSession."""

from __future__ import annotations

from collections.abc import Callable

from backend.infrastructure.conversations.sqlite_stores import (
    SQLiteConversationMetadataRepository,
)


class LegacyConversationMetadataRepository(SQLiteConversationMetadataRepository):
    """Compatibility name retained by the current composition root."""


class QuickChatThreadGateway:
    def __init__(self, session_provider: Callable):
        self._session_provider = session_provider

    async def load_messages(self, thread_id: str):
        return await self._session_provider().load_thread(thread_id)

    async def pending_approval(self, thread_id: str):
        return await self._session_provider().pending_approval(thread_id)

    async def delete(self, thread_id: str) -> None:
        await self._session_provider().delete_thread(thread_id)


class QuickChatRunGateway:
    def __init__(self, session_provider: Callable):
        self._session_provider = session_provider

    def stream(self, message: str, **kwargs):
        return self._session_provider().astream(message, **kwargs)

    async def claim_approval(self, **kwargs):
        return await self._session_provider().claim_approval(**kwargs)

    def resume(self, *, claim, **kwargs):
        return self._session_provider().aresume(_claim=claim, **kwargs)
