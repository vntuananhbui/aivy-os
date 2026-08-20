from backend.api.routes import conversations as canonical
from api.routes import conversations as legacy
from backend.api.routes import chat as canonical_chat
from api.routes import chat as legacy_chat


def test_legacy_conversation_route_is_canonical_facade() -> None:
    assert legacy.router is canonical.router
    assert legacy.list_conversations is canonical.list_conversations
    assert legacy.get_conversation is canonical.get_conversation
    assert legacy.delete_conversation is canonical.delete_conversation


def test_legacy_chat_route_is_canonical_facade() -> None:
    assert legacy_chat.router is canonical_chat.router
    assert legacy_chat.create_chat is canonical_chat.create_chat
    assert legacy_chat.resume_chat is canonical_chat.resume_chat
