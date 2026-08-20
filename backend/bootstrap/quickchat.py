"""QuickChat composition root for the current single-process deployment."""

from __future__ import annotations

from typing import Any

from backend.application.conversations.service import ConversationService
from backend.application.chat_runs.service import ChatRunService
from backend.infrastructure.conversations.legacy import (
    LegacyConversationMetadataRepository,
    QuickChatThreadGateway,
    QuickChatRunGateway,
)
from backend.infrastructure.conversations.sqlite_stores import action_workflow_repository

_chat_session: Any = None


def get_chat_session():
    global _chat_session
    if _chat_session is None:
        from ai.quickchat.session import ChatSession

        _chat_session = ChatSession(
            conversation_metadata=conversation_metadata_repository,
            action_workflows=action_workflow_repository,
        )
    return _chat_session


conversation_metadata_repository = LegacyConversationMetadataRepository()
conversation_thread_gateway = QuickChatThreadGateway(get_chat_session)
chat_runtime_gateway = QuickChatRunGateway(get_chat_session)
chat_run_service = ChatRunService(chat_runtime_gateway)
conversation_service = ConversationService(
    metadata=conversation_metadata_repository,
    threads=conversation_thread_gateway,
)
