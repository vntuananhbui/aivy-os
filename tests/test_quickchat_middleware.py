from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ai.quickchat.middleware import _compact_historical_tools, _strip_reasoning


def test_strip_reasoning_removes_provider_cot_but_preserves_answer_and_tools() -> None:
    message = AIMessage(
        content="Final answer",
        additional_kwargs={"reasoning_content": "very long thought", "provider_field": "keep"},
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "call-1"}],
    )

    sanitized = _strip_reasoning(message)

    assert sanitized.content == "Final answer"
    assert sanitized.additional_kwargs == {"provider_field": "keep"}
    assert sanitized.tool_calls == message.tool_calls


def test_strip_reasoning_leaves_non_ai_messages_unchanged() -> None:
    message = HumanMessage(content="hello")

    assert _strip_reasoning(message) is message


def test_only_historical_tool_results_are_compacted() -> None:
    historical = "old" * 2_000
    current = "new" * 2_000
    messages = [
        HumanMessage(content="first"),
        AIMessage(content="", tool_calls=[{"name": "read", "args": {}, "id": "old-call"}]),
        ToolMessage(content=historical, tool_call_id="old-call"),
        AIMessage(content="previous answer"),
        HumanMessage(content="follow up"),
        AIMessage(content="", tool_calls=[{"name": "read", "args": {}, "id": "new-call"}]),
        ToolMessage(content=current, tool_call_id="new-call"),
    ]

    compacted, removed = _compact_historical_tools(messages)

    assert removed > 0
    assert len(compacted[2].content) <= 3_000
    assert compacted[2].tool_call_id == "old-call"
    assert compacted[6].content == current
