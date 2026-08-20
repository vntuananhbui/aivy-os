"""Short-lived OAuth state repository contracts and local implementation."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable
from typing import Protocol


class OAuthStateRepository(Protocol):
    async def create(self) -> str: ...

    async def consume(self, state: str) -> bool: ...


class InMemoryOAuthStateRepository:
    """Single-process adapter used until Redis/PostgreSQL persistence lands."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300,
        clock: Callable[[], float] = time.time,
        token_factory: Callable[[int], str] = secrets.token_urlsafe,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._token_factory = token_factory
        self._states: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> str:
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            state = self._token_factory(24)
            self._states[state] = now
            return state

    async def consume(self, state: str) -> bool:
        if not state:
            return False
        async with self._lock:
            created_at = self._states.pop(state, None)
            if created_at is None:
                return False
            return self._clock() - created_at <= self.ttl_seconds

    def _purge_expired(self, now: float) -> None:
        for state, created_at in list(self._states.items()):
            if now - created_at > self.ttl_seconds:
                del self._states[state]

