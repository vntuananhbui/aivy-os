from __future__ import annotations

import json

from ai.research.orchestration.conversation_context import build_preamble
from ai.research.telemetry.models import ConversationMessage
from ai.research.telemetry.ports import InMemoryResearchTelemetryFactory
from backend.infrastructure.research.conversation_history import conversation_turns
from backend.infrastructure.research.telemetry import (
    FilesystemResearchTelemetryFactory,
)
from backend.infrastructure.research.workspace_factory import (
    FilesystemResearchWorkspaceFactory,
)
from searchos.socm.state import SearchState


def test_filesystem_factory_persists_and_hydrates_conversation(tmp_path) -> None:
    path = tmp_path / "conversation.json"
    factory = FilesystemResearchTelemetryFactory()

    first = factory.create_conversation_logger(path)
    first.log(ConversationMessage(role="user", content="first"))

    second = factory.create_conversation_logger(path)
    second.hydrate()
    second.log(ConversationMessage(role="assistant", content="second"))

    record = json.loads(
        (tmp_path / "conversations" / "orchestrator.json").read_text(
            encoding="utf-8"
        )
    )
    assert [message["content"] for message in record["messages"]] == [
        "first",
        "second",
    ]


def test_filesystem_factory_persists_trajectory_and_notifies_listener(tmp_path) -> None:
    path = tmp_path / "trajectory.jsonl"
    logger = FilesystemResearchTelemetryFactory().create_trajectory_logger(path)
    observed: list[dict] = []
    logger.add_listener(observed.append)

    logger._append_raw({"type": "step", "action": "search"})

    assert json.loads(path.read_text(encoding="utf-8"))["action"] == "search"
    assert logger.tool_counts == {"search": 1}
    assert observed[0]["type"] == "step"
    assert observed[0]["action"] == "search"
    assert observed[0]["timestamp"]


def test_in_memory_factory_does_not_touch_filesystem(tmp_path) -> None:
    path = tmp_path / "unused.jsonl"
    logger = InMemoryResearchTelemetryFactory().create_trajectory_logger(path)

    logger._append_raw({"type": "step", "action": "open"})

    assert logger.tool_counts == {"open": 1}
    assert not path.exists()


def test_workspace_factory_round_trips_search_state(tmp_path) -> None:
    workspace = FilesystemResearchWorkspaceFactory().create_workspace(
        tmp_path, "session-1"
    )
    workspace.create()
    workspace.save_state(SearchState(intent="research question"))

    assert workspace.session_id == "session-1"
    assert workspace.load_state().intent == "research question"
    assert (workspace.path / "search_state.json").exists()


def test_conversation_reader_and_preamble_have_separate_ownership(tmp_path) -> None:
    conversation_dir = tmp_path / "conversations"
    conversation_dir.mkdir()
    (conversation_dir / "orchestrator.json").write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": "Answer"},
                ]
            }
        ),
        encoding="utf-8",
    )

    turns = conversation_turns(tmp_path)

    assert turns == [{"query": "Question", "answer": "Answer", "steers": []}]
    assert "Question" in build_preamble(turns)
    assert "Answer" in build_preamble(turns)
