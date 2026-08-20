"""SQLite implementations for QuickChat product metadata and HITL workflows."""

from __future__ import annotations

import asyncio
import sqlite3
import time

from backend.application.chat_runs.models import ActionWorkflow, WorkflowStatus
from backend.application.conversations.models import ConversationSummary
from backend.infrastructure.database import quickchat_sqlite

_ACTIVE_STATUSES = ("collecting", "awaiting_approval", "resuming")
_TITLE_MAX_CHARS = 60


def _connect() -> sqlite3.Connection:
    path = quickchat_sqlite.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


class SQLiteConversationMetadataRepository:
    @staticmethod
    def _title(first_message: str) -> str:
        text = " ".join(first_message.split())
        return text if len(text) <= _TITLE_MAX_CHARS else text[:_TITLE_MAX_CHARS].rstrip() + "…"

    def _touch(self, thread_id: str, first_message: str | None) -> None:
        connection = _connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS conversations ("
                "thread_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            now = time.time()
            connection.execute(
                "INSERT INTO conversations (thread_id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(thread_id) DO UPDATE SET "
                "updated_at = excluded.updated_at",
                (thread_id, self._title(first_message or "New chat"), now, now),
            )
            connection.commit()
        finally:
            connection.close()

    async def touch(self, thread_id: str, first_message: str | None = None) -> None:
        await asyncio.to_thread(self._touch, thread_id, first_message)

    def _list(self, limit: int) -> list[ConversationSummary]:
        connection = _connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS conversations ("
                "thread_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            rows = connection.execute(
                "SELECT thread_id, title, created_at, updated_at FROM conversations "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [ConversationSummary(*row) for row in rows]
        finally:
            connection.close()

    async def list(self, *, limit: int = 100) -> list[ConversationSummary]:
        return await asyncio.to_thread(self._list, limit)

    def _delete(self, thread_id: str) -> None:
        connection = _connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS conversations ("
                "thread_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            connection.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
            connection.commit()
        finally:
            connection.close()

    async def delete(self, thread_id: str) -> None:
        await asyncio.to_thread(self._delete, thread_id)


class SQLiteActionWorkflowRepository:
    @staticmethod
    def _prepare(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS chat_action_workflows ("
            "thread_id TEXT PRIMARY KEY, agent_type TEXT NOT NULL, status TEXT NOT NULL, "
            "interrupt_id TEXT, thinking INTEGER NOT NULL, effort TEXT NOT NULL, "
            "graph_build_key TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0, "
            "lease_owner TEXT, lease_expires_at REAL, created_at REAL NOT NULL, "
            "updated_at REAL NOT NULL, CHECK(status IN ('collecting','awaiting_approval',"
            "'resuming','completed','cancelled','expired')))"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS action_workflows_status_updated_idx "
            "ON chat_action_workflows(status, updated_at)"
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | None) -> ActionWorkflow | None:
        if row is None:
            return None
        return ActionWorkflow(
            thread_id=row["thread_id"], agent_type=row["agent_type"], status=row["status"],
            interrupt_id=row["interrupt_id"], thinking=bool(row["thinking"]),
            effort=row["effort"], graph_build_key=row["graph_build_key"],
            version=row["version"], lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"], created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _upsert(self, thread_id, agent_type, status, thinking, effort, graph_build_key, interrupt_id):
        connection = _connect()
        try:
            self._prepare(connection)
            now = time.time()
            connection.execute(
                "INSERT INTO chat_action_workflows "
                "(thread_id, agent_type, status, interrupt_id, thinking, effort, graph_build_key, "
                "version, lease_owner, lease_expires_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, ?, ?) "
                "ON CONFLICT(thread_id) DO UPDATE SET agent_type=excluded.agent_type, "
                "status=excluded.status, interrupt_id=excluded.interrupt_id, "
                "thinking=excluded.thinking, effort=excluded.effort, "
                "graph_build_key=excluded.graph_build_key, "
                "version=chat_action_workflows.version + 1, lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=excluded.updated_at",
                (thread_id, agent_type, status, interrupt_id, int(thinking), effort, graph_build_key, now, now),
            )
            connection.commit()
            return self._from_row(connection.execute(
                "SELECT * FROM chat_action_workflows WHERE thread_id = ?", (thread_id,)
            ).fetchone())
        finally:
            connection.close()

    async def upsert(self, thread_id: str, *, agent_type: str, status: WorkflowStatus, thinking: bool, effort: str, graph_build_key: str, interrupt_id: str | None = None) -> ActionWorkflow:
        result = await asyncio.to_thread(self._upsert, thread_id, agent_type, status, thinking, effort, graph_build_key, interrupt_id)
        assert result is not None
        return result

    def _get(self, thread_id: str, active_only: bool):
        connection = _connect()
        try:
            self._prepare(connection)
            if active_only:
                placeholders = ",".join("?" for _ in _ACTIVE_STATUSES)
                row = connection.execute(
                    f"SELECT * FROM chat_action_workflows WHERE thread_id = ? AND status IN ({placeholders})",
                    (thread_id, *_ACTIVE_STATUSES),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM chat_action_workflows WHERE thread_id = ?", (thread_id,)
                ).fetchone()
            return self._from_row(row)
        finally:
            connection.close()

    async def get(self, thread_id: str, *, active_only: bool = False) -> ActionWorkflow | None:
        return await asyncio.to_thread(self._get, thread_id, active_only)

    def _acquire(self, thread_id, interrupt_id, lease_owner, lease_seconds):
        connection = _connect()
        try:
            self._prepare(connection)
            now = time.time()
            cursor = connection.execute(
                "UPDATE chat_action_workflows SET status='resuming', lease_owner=?, "
                "lease_expires_at=?, version=version+1, updated_at=? WHERE thread_id=? "
                "AND interrupt_id=? AND status='awaiting_approval'",
                (lease_owner, now + lease_seconds, now, thread_id, interrupt_id),
            )
            connection.commit()
            if cursor.rowcount != 1:
                return None
            return self._from_row(connection.execute(
                "SELECT * FROM chat_action_workflows WHERE thread_id = ?", (thread_id,)
            ).fetchone())
        finally:
            connection.close()

    async def acquire_resume_lease(self, thread_id: str, interrupt_id: str, lease_owner: str, *, lease_seconds: float = 120.0) -> ActionWorkflow | None:
        return await asyncio.to_thread(self._acquire, thread_id, interrupt_id, lease_owner, lease_seconds)

    def _finish(self, thread_id, lease_owner, status):
        if status not in ("collecting", "awaiting_approval", "completed", "cancelled", "expired"):
            raise ValueError(f"invalid post-resume workflow status: {status}")
        connection = _connect()
        try:
            self._prepare(connection)
            cursor = connection.execute(
                "UPDATE chat_action_workflows SET status=?, "
                "interrupt_id=CASE WHEN ?='awaiting_approval' THEN interrupt_id ELSE NULL END, "
                "lease_owner=NULL, lease_expires_at=NULL, version=version+1, updated_at=? "
                "WHERE thread_id=? AND lease_owner=? AND status='resuming'",
                (status, status, time.time(), thread_id, lease_owner),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            connection.close()

    async def finish_resume(self, thread_id: str, lease_owner: str, *, status: WorkflowStatus) -> bool:
        return await asyncio.to_thread(self._finish, thread_id, lease_owner, status)

    def _delete(self, thread_id):
        connection = _connect()
        try:
            self._prepare(connection)
            connection.execute("DELETE FROM chat_action_workflows WHERE thread_id = ?", (thread_id,))
            connection.commit()
        finally:
            connection.close()

    async def delete(self, thread_id: str) -> None:
        await asyncio.to_thread(self._delete, thread_id)


conversation_metadata_repository = SQLiteConversationMetadataRepository()
action_workflow_repository = SQLiteActionWorkflowRepository()
