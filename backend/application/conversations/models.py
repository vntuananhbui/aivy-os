"""Framework-neutral conversation DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversationSummary:
    thread_id: str
    title: str
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class ConversationDetail:
    thread_id: str
    messages: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None
