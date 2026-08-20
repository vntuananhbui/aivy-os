"""Ports consumed by conversation application services."""

from __future__ import annotations

from typing import Any, Protocol

from backend.application.conversations.models import ConversationSummary


class ConversationMetadataRepository(Protocol):
    async def list(self, *, limit: int = 100) -> list[ConversationSummary]: ...

    async def delete(self, thread_id: str) -> None: ...


class ConversationThreadGateway(Protocol):
    async def load_messages(self, thread_id: str) -> list[dict[str, Any]] | None: ...

    async def pending_approval(self, thread_id: str) -> dict[str, Any] | None: ...

    async def delete(self, thread_id: str) -> None: ...
