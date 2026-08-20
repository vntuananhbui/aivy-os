"""Compatibility facade for canonical backend QuickChat routes."""

from backend.api.routes.chat import (  # noqa: F401
    ChatRequest,
    ChatResumeRequest,
    create_chat,
    resume_chat,
    router,
)
from backend.bootstrap.quickchat import get_chat_session as _get_chat_session

__all__ = [
    "ChatRequest",
    "ChatResumeRequest",
    "_get_chat_session",
    "create_chat",
    "resume_chat",
    "router",
]
