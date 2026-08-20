"""Structured QuickChat intent router for action-agent handoff."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    route: Literal["normal_chat", "teams_meeting_action"]
    request: str = Field(description="The complete user request to hand to the selected route")


_ROUTER_PROMPT = """Classify the user's latest request for QuickChat.

Choose teams_meeting_action only when the user explicitly wants the system to
create or schedule a Microsoft Teams meeting or generate a new Teams meeting
link. Questions about Teams, instructions, documentation, existing meetings,
or general calendar advice are normal_chat. When uncertain, choose normal_chat.
Preserve the user's request exactly enough for the selected agent to act on it.
"""


async def route_request(message: str) -> RouteDecision:
    from searchos.config.models import get_model_for

    router = get_model_for("chat").with_structured_output(RouteDecision)
    result = await router.ainvoke(
        [SystemMessage(content=_ROUTER_PROMPT), HumanMessage(content=message)]
    )
    if isinstance(result, RouteDecision):
        return result
    return RouteDecision.model_validate(result)
