"""Persistence ports consumed by the QuickChat AI runtime.

The backend composition root supplies concrete repositories.  Keeping these
small protocols beside the consumer prevents ``ChatSession`` from selecting a
database implementation or importing backend infrastructure.
"""

from __future__ import annotations

from typing import Any, Protocol


class ConversationMetadataPort(Protocol):
    async def touch(self, thread_id: str, first_message: str | None = None) -> None: ...


class ActionWorkflowPort(Protocol):
    async def upsert(self, thread_id: str, **kwargs: Any) -> Any: ...

    async def get(self, thread_id: str, *, active_only: bool = False) -> Any: ...

    async def acquire_resume_lease(
        self,
        thread_id: str,
        interrupt_id: str,
        lease_owner: str,
        *,
        lease_seconds: float = 120.0,
    ) -> Any: ...

    async def finish_resume(self, thread_id: str, lease_owner: str, **kwargs: Any) -> bool: ...

    async def delete(self, thread_id: str) -> None: ...
