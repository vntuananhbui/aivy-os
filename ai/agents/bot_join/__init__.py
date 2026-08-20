"""Temporary `/bot-join` command agent.

The tool currently validates and echoes a Teams join URL. It deliberately has
no browser/meeting side effect yet, so it does not require human approval.
"""

from __future__ import annotations

from urllib.parse import urlparse

from langchain_core.tools import tool

AGENT_TYPE = "bot_join"
DESCRIPTION = "Validate a Teams join URL and print the temporary bot-joined stub result."


@tool
def bot_join(teams_join_url: str) -> str:
    """Temporarily simulate joining a bot to one Microsoft Teams meeting URL.

    Args:
        teams_join_url: Full HTTPS Microsoft Teams join URL.
    """
    clean_url = teams_join_url.strip()
    parsed = urlparse(clean_url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in {"teams.microsoft.com", "teams.live.com"}:
        return "Lỗi: vui lòng cung cấp một Microsoft Teams join URL hợp lệ."
    return f"Bot đã vào link {clean_url}"


def get_tools() -> list:
    return [bot_join]


def build_agent(*, checkpointer=None, thinking: bool = True, effort: str = "medium"):
    from langchain.agents import create_agent

    from ai.quickchat.agent import CHAT_EFFORT_TO_REASONING
    from ai.quickchat.middleware import build_middleware_stack
    from searchos.config.models import get_model_for, resolve_profile

    reasoning_effort = None
    if resolve_profile("chat").enable_thinking:
        reasoning_effort = CHAT_EFFORT_TO_REASONING.get(effort, "low") if thinking else "none"
    return create_agent(
        model=get_model_for("chat", reasoning_effort=reasoning_effort),
        tools=get_tools(),
        system_prompt=(
            "You are BotJoin, dispatched by /bot-join. The remaining user message must "
            "contain exactly one Microsoft Teams join URL. Call bot_join exactly once with "
            "that URL, then return its result verbatim with no additional claims. This is "
            "currently a stub and performs no real meeting side effect. If no URL is given, "
            "ask for one instead of calling the tool."
        ),
        checkpointer=checkpointer,
        middleware=build_middleware_stack(role="chat"),
    )
