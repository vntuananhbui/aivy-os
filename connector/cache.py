"""Shared content cache for connectors — freshness-keyed, not a pre-index.

Any connector (SharePoint, Outlook, ...) can use this to avoid re-downloading
+ re-parsing unchanged content across chat turns/sessions: cache a fetched
item keyed by ``(source, item_id)`` alongside the source system's own
freshness marker (e.g. Graph's ``lastModifiedDateTime``); a caller re-fetches
only when that marker changes.

SQLite in WAL mode so concurrent reads/writes from deep-research's parallel
sub-agents don't deadlock each other; every call runs the blocking sqlite3
calls in a thread since this module is used from async code.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path.home() / ".cache" / "searchos" / "connector_cache.db"


@dataclass
class CachedContent:
    source: str
    item_id: str
    name: str
    content: str
    last_modified: str
    fetched_at: float


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "source TEXT NOT NULL, item_id TEXT NOT NULL, name TEXT NOT NULL, "
        "content TEXT NOT NULL, last_modified TEXT NOT NULL, fetched_at REAL NOT NULL, "
        "PRIMARY KEY (source, item_id))"
    )
    return conn


def _get_sync(source: str, item_id: str) -> CachedContent | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT source, item_id, name, content, last_modified, fetched_at "
            "FROM cache WHERE source = ? AND item_id = ?",
            (source, item_id),
        ).fetchone()
    finally:
        conn.close()
    return CachedContent(*row) if row else None


def _put_sync(source: str, item_id: str, name: str, content: str, last_modified: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO cache (source, item_id, name, content, last_modified, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (source, item_id) DO UPDATE SET "
            "name = excluded.name, content = excluded.content, "
            "last_modified = excluded.last_modified, fetched_at = excluded.fetched_at",
            (source, item_id, name, content, last_modified, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def _purge_sync(source: str, item_ids: list[str]) -> int:
    if not item_ids:
        return 0
    conn = _connect()
    try:
        placeholders = ",".join("?" for _ in item_ids)
        cur = conn.execute(
            f"DELETE FROM cache WHERE source = ? AND item_id IN ({placeholders})",
            (source, *item_ids),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _purge_all_sync(source: str | None) -> int:
    conn = _connect()
    try:
        if source is None:
            cur = conn.execute("DELETE FROM cache")
        else:
            cur = conn.execute("DELETE FROM cache WHERE source = ?", (source,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _list_cached_ids_sync(source: str) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT item_id FROM cache WHERE source = ?", (source,)).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


async def get(source: str, item_id: str) -> CachedContent | None:
    return await asyncio.to_thread(_get_sync, source, item_id)


async def put(source: str, item_id: str, name: str, content: str, last_modified: str) -> None:
    await asyncio.to_thread(_put_sync, source, item_id, name, content, last_modified)


async def purge(source: str, item_ids: list[str]) -> int:
    return await asyncio.to_thread(_purge_sync, source, item_ids)


async def purge_all(source: str | None = None) -> int:
    return await asyncio.to_thread(_purge_all_sync, source)


async def list_cached_ids(source: str) -> list[str]:
    return await asyncio.to_thread(_list_cached_ids_sync, source)
