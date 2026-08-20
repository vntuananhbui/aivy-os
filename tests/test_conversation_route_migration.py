from backend.api.routes import conversations as canonical
from backend.api.routes import chat as canonical_chat


def test_conversation_routes_are_backend_owned() -> None:
    assert canonical.list_conversations.__module__ == "backend.api.routes.conversations"
    assert canonical.get_conversation.__module__ == "backend.api.routes.conversations"
    assert canonical.delete_conversation.__module__ == "backend.api.routes.conversations"


def test_chat_routes_are_backend_owned() -> None:
    assert canonical_chat.create_chat.__module__ == "backend.api.routes.chat"
    assert canonical_chat.resume_chat.__module__ == "backend.api.routes.chat"
