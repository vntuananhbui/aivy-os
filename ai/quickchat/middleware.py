"""Middleware stack for the main quickchat agent (``build_chat_agent``).

Separate from ``ai/quickchat/sources/source_agent.py``'s per-sub-agent
``middleware`` param — that's a seam for a future *complexity router* on one
sub-agent; this is what the OUTER (user-facing) agent uses, built once per
``build_chat_agent`` call.

Each middleware is wired defensively (best-effort, logged, never raises) —
a broken/unconfigured middleware should degrade quickchat, not crash it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelFallbackMiddleware,
    SummarizationMiddleware,
)
from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

# ("tokens", N): summarize once the conversation crosses N tokens.
_SUMMARIZATION_TRIGGER = ("tokens", 10_000)
# ("messages", N): always keep the last N messages verbatim (un-summarized).
_SUMMARIZATION_KEEP = ("messages", 8)

_REASONING_KEYS = {"reasoning", "reasoning_content", "thinking"}
_HISTORICAL_TOOL_MAX_CHARS = 3_000


def _strip_reasoning(message: Any) -> Any:
    """Return an AI message without provider-specific historical CoT data."""
    if not isinstance(message, AIMessage):
        return message
    additional = {
        key: value
        for key, value in message.additional_kwargs.items()
        if key not in _REASONING_KEYS
    }
    content = message.content
    if isinstance(content, list):
        content = [
            block
            for block in content
            if not (isinstance(block, dict) and block.get("type") in _REASONING_KEYS)
        ]
    return message.model_copy(update={"additional_kwargs": additional, "content": content})


def _compact_historical_tools(messages: list[Any]) -> tuple[list[Any], int]:
    """Cap tool payloads before the latest user turn while preserving protocol."""
    latest_human = max(
        (index for index, message in enumerate(messages) if message.type == "human"),
        default=-1,
    )
    compacted: list[Any] = []
    removed_chars = 0
    for index, message in enumerate(messages):
        content = message.content
        if (
            index < latest_human
            and isinstance(message, ToolMessage)
            and isinstance(content, str)
            and len(content) > _HISTORICAL_TOOL_MAX_CHARS
        ):
            head_chars = _HISTORICAL_TOOL_MAX_CHARS - 600
            shortened = (
                content[:head_chars]
                + "\n\n[historical tool result compacted]\n\n"
                + content[-500:]
            )
            removed_chars += len(content) - len(shortened)
            message = message.model_copy(update={"content": shortened})
        compacted.append(message)
    return compacted, removed_chars


class QuickChatContextMiddleware(AgentMiddleware):
    """Keep persisted history useful without resending raw chain-of-thought."""

    async def awrap_model_call(self, request: Any, handler: Callable) -> Any:
        original = request.messages
        sanitized = [_strip_reasoning(message) for message in original]
        sanitized, compacted_tool_chars = _compact_historical_tools(sanitized)
        input_chars = sum(len(str(message.content)) for message in sanitized)
        stripped_chars = sum(
            len(str(message.additional_kwargs.get("reasoning_content", "")))
            for message in original
            if isinstance(message, AIMessage)
        )
        tool_chars = sum(
            len(str(message.content)) for message in sanitized if message.type == "tool"
        )
        logger.info(
            "quickchat.model_input: messages={} chars={} tool_chars={} "
            "stripped_reasoning_chars={} compacted_tool_chars={}",
            len(sanitized),
            input_chars,
            tool_chars,
            stripped_chars,
            compacted_tool_chars,
        )
        return await handler(replace(request, messages=sanitized))


def build_middleware_stack(*, role: str = "chat") -> list[AgentMiddleware]:
    """Build the middleware list for ``create_agent(middleware=...)``.

    - **ModelFallbackMiddleware** — only added when ``role`` has a fallback
      configured (Settings UI "Roles" section, "Fallback" column — see
      ``searchos/config/settings.py::Settings.fallback_roles``). That field
      stores a **profile name directly** (not another role), resolved via
      ``get_model_for_profile`` — deliberately no role indirection on the
      fallback side, since a fallback is "this one other model", not a role
      of its own. Pick a fallback on a genuinely different provider —
      same-provider fallbacks share the primary's outage.
    - **LLMToolSelectorMiddleware** — tried, **reverted**. It runs its own
      internal model call to pick tools, but that call streams under the
      same LangGraph ``"model"`` node as the main agent's real call (a
      middleware wraps the node, it isn't a separate node) — quickchat's
      streaming filter (``session.py``) can only key off ``langgraph_node``,
      so it can't tell the two apart. Result: the selector's own raw output
      (``{"tools": [...]}``, its own system-prompt reasoning) leaked into
      the user-visible answer/reasoning stream, and it also visibly confused
      the main model into writing literal ``<tool>...</tool>`` text instead
      of a real tool call. Not safe to use with token-level streaming until
      that's solved (e.g. tagging/filtering by call site, not just node
      name) — do not re-add without fixing the streaming-isolation problem
      first.
    - **SummarizationMiddleware** — summarizes older messages once the
      conversation crosses ``_SUMMARIZATION_TRIGGER``, keeping the last
      ``_SUMMARIZATION_KEEP`` messages intact. More relevant now that
      quickchat has persistent history (``ai/quickchat/persistence/``) —
      conversations can span many turns across days.
    """
    from searchos.config.models import get_model_for, get_model_for_profile
    from searchos.config.settings import settings

    middleware: list[AgentMiddleware] = [QuickChatContextMiddleware()]

    fallback_profile = settings.fallback_roles.get(role)
    if fallback_profile:
        try:
            primary_model = get_model_for(role)
            fallback_model = get_model_for_profile(
                fallback_profile, tracking_label=f"{role}:fallback"
            )
            middleware.append(ModelFallbackMiddleware(primary_model, fallback_model))
        except Exception as exc:
            logger.warning(
                "ai.quickchat.middleware: failed to wire ModelFallbackMiddleware for role {!r}: {}",
                role,
                exc,
            )

    try:
        summarization_model = get_model_for(role)
        middleware.append(
            SummarizationMiddleware(
                model=summarization_model,
                trigger=[_SUMMARIZATION_TRIGGER],
                keep=_SUMMARIZATION_KEEP,
            )
        )
    except Exception as exc:
        logger.warning("ai.quickchat.middleware: failed to wire SummarizationMiddleware: {}", exc)

    return middleware
