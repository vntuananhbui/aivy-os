"""Compatibility facade for research conversation context helpers."""

from ai.research.orchestration.conversation_context import (
    MAX_ANSWER_CHARS,
    MAX_TURNS,
    build_preamble,
)
from backend.infrastructure.research.conversation_history import conversation_turns

__all__ = [
    "MAX_ANSWER_CHARS",
    "MAX_TURNS",
    "build_preamble",
    "conversation_turns",
]
