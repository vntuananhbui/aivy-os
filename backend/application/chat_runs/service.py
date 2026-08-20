"""Application service for starting and resuming live QuickChat turns."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from backend.application.chat_runs.gateways import ChatRuntimeGateway


class ChatRunService:
    def __init__(self, runtime: ChatRuntimeGateway) -> None:
        self._runtime = runtime

    def stream(
        self,
        message: str,
        *,
        thread_id: str,
        thinking: bool = False,
        effort: str = "medium",
        web_search_enabled: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        return self._runtime.stream(
            message,
            thread_id=thread_id,
            thinking=thinking,
            effort=effort,
            web_search_enabled=web_search_enabled,
        )

    async def claim_approval(
        self, *, thread_id: str, interrupt_id: str
    ) -> tuple[Any, str] | None:
        return await self._runtime.claim_approval(
            thread_id=thread_id,
            interrupt_id=interrupt_id,
        )

    def resume(
        self,
        *,
        thread_id: str,
        interrupt_id: str,
        decision: str,
        message: str = "",
        claim: tuple[Any, str],
    ) -> AsyncIterator[dict[str, Any]]:
        if decision == "other" and not message.strip():
            raise ValueError("Other requires non-empty feedback.")
        return self._runtime.resume(
            thread_id=thread_id,
            interrupt_id=interrupt_id,
            decision=decision,
            message=message,
            claim=claim,
        )
