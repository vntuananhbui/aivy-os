"""AI runtime port used by the live chat application service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ChatRuntimeGateway(Protocol):
    def stream(
        self,
        message: str,
        *,
        thread_id: str,
        thinking: bool,
        effort: str,
        web_search_enabled: bool,
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def claim_approval(
        self, *, thread_id: str, interrupt_id: str
    ) -> tuple[Any, str] | None: ...

    def resume(
        self,
        *,
        thread_id: str,
        interrupt_id: str,
        decision: str,
        message: str,
        claim: tuple[Any, str],
    ) -> AsyncIterator[dict[str, Any]]: ...
