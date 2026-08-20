"""Application-level action workflow state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkflowStatus = Literal[
    "collecting",
    "awaiting_approval",
    "resuming",
    "completed",
    "cancelled",
    "expired",
]


@dataclass(frozen=True)
class ActionWorkflow:
    thread_id: str
    agent_type: str
    status: WorkflowStatus
    interrupt_id: str | None
    thinking: bool
    effort: str
    graph_build_key: str
    version: int
    lease_owner: str | None
    lease_expires_at: float | None
    created_at: float
    updated_at: float
