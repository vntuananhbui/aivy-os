"""Quickchat's LangGraph checkpointer — process-lifetime singleton, set once
by the FastAPI app at startup.

Production persistence is constructed by backend infrastructure and injected
here once at application startup. SQLite/Postgres savers both implement the
same ``BaseCheckpointSaver`` interface, so nothing in ``agent.py`` or
``session.py`` depends on the selected database.

Callers outside the FastAPI app (CLI scripts, tests) that never call
``set_checkpointer`` get an in-memory ``MemorySaver()`` fallback — same
behavior as before this change, just not the default anymore.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

_checkpointer: BaseCheckpointSaver | None = None


def set_checkpointer(checkpointer: BaseCheckpointSaver | None) -> None:
    global _checkpointer
    _checkpointer = checkpointer


def get_checkpointer() -> BaseCheckpointSaver:
    if _checkpointer is not None:
        return _checkpointer
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
