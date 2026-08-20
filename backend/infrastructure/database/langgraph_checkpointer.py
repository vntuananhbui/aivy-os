"""Concrete LangGraph checkpointer factories owned by backend infrastructure."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.infrastructure.database.quickchat_sqlite import DB_PATH


@asynccontextmanager
async def create_sqlite_checkpointer() -> AsyncGenerator[BaseCheckpointSaver, None]:
    """Open and initialize the local SQLite saver for the app lifetime."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
