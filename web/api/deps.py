"""Compatibility facade for backend runtime composition state."""

from backend.bootstrap.runtime import (
    ENV_FILE_PATH,
    WEB_SETTINGS_PATH,
    WORKSPACE_ROOT,
    get_llm,
    init_search_provider,
)

__all__ = [
    "ENV_FILE_PATH",
    "WEB_SETTINGS_PATH",
    "WORKSPACE_ROOT",
    "get_llm",
    "init_search_provider",
]
