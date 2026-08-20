"""Canonical SearchOS FastAPI application entry point.

Most route modules still live in the legacy ``web/api`` package during the
incremental migration. This module owns app assembly now; legacy
``api.main:app`` only re-exports the application from here.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Transitional import bridge: legacy route modules are still importable as
# ``api.*`` from ``web/``. Remove when they have all moved under ``backend``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_WEB_ROOT = _REPO_ROOT / "web"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_LEGACY_WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LEGACY_WEB_ROOT))

from api import settings_store  # noqa: E402
from api.routes import (  # noqa: E402
    connectors,
    diagnostics,
    models,
    settings,
    workspace,
)
from backend.api.routes import chat, conversations, history, search, stream  # noqa: E402
from poc.api.routes import router as poc_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings_store.load_and_apply()

    from ai.quickchat.persistence.checkpointer import set_checkpointer
    from backend.infrastructure.database.langgraph_checkpointer import create_sqlite_checkpointer

    from poc import scheduler as poc_scheduler

    async with create_sqlite_checkpointer() as checkpointer:
        set_checkpointer(checkpointer)
        await poc_scheduler.start_loop()
        yield
        await poc_scheduler.stop_loop()
    set_checkpointer(None)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SearchOS API",
        version="0.1.0",
        description="SearchOS — agentic search harness, REST + WebSocket API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(search.router)
    app.include_router(workspace.router)
    app.include_router(stream.router)
    app.include_router(history.router)
    app.include_router(settings.router)
    app.include_router(models.router)
    app.include_router(diagnostics.router)
    app.include_router(connectors.router)
    app.include_router(poc_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
