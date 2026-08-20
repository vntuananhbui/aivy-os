"""Compatibility facade for the canonical backend conversation routes."""

from backend.api.routes.conversations import (  # noqa: F401
    delete_conversation,
    get_conversation,
    list_conversations,
    router,
)

__all__ = [
    "delete_conversation",
    "get_conversation",
    "list_conversations",
    "router",
]
