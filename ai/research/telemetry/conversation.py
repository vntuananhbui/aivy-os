"""Pure conversion helpers for research conversation telemetry."""

from __future__ import annotations

from typing import Any

from ai.research.telemetry.models import ConversationMessage


def langchain_msg_to_conversation_msgs(msg: Any) -> list[ConversationMessage]:
    """Convert one LangChain message into storage-neutral telemetry models."""
    results: list[ConversationMessage] = []
    msg_type = getattr(msg, "type", None)
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        content = str(content)

    if msg_type == "human":
        results.append(ConversationMessage(role="user", content=content))
    elif msg_type == "ai":
        reasoning = ""
        extras = getattr(msg, "additional_kwargs", None) or {}
        if isinstance(extras, dict):
            reasoning = extras.get("reasoning_content", "") or ""
        results.append(ConversationMessage(
            role="assistant", content=content, reasoning=reasoning,
        ))
        for tool_call in getattr(msg, "tool_calls", []) or []:
            results.append(ConversationMessage(
                role="tool_call",
                tool_name=(tool_call.get("name") or ""),
                tool_call_id=(tool_call.get("id") or ""),
                content=str(tool_call.get("args") or ""),
            ))
    elif msg_type == "tool":
        results.append(ConversationMessage(
            role="tool_result",
            tool_name=(getattr(msg, "name", "") or ""),
            tool_call_id=(getattr(msg, "tool_call_id", "") or ""),
            content=content,
        ))
    return results


__all__ = ["langchain_msg_to_conversation_msgs"]
