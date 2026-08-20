"""Application state for a live research run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ResearchRunStatus = Literal["running", "completed", "error"]


@dataclass
class ResearchRun:
    session_id: str
    status: ResearchRunStatus
    result: Any = None
    error: str | None = None
    task: Any = None
    harness: Any = None
    initial_state: Any = None
    steer_queue: Any = None


__all__ = ["ResearchRun", "ResearchRunStatus"]
