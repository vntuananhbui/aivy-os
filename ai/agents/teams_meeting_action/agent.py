"""Build the Teams meeting action agent with a mandatory final approval gate."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from ai.adapters.connectors.calendar import list_calendar_events
from ai.agents.teams_meeting_action.prompts import SYSTEM_PROMPT
from ai.agents.teams_meeting_action.tools import check_calendar_conflicts, create_teams_meeting

AGENT_TYPE = "teams_meeting_action"
DESCRIPTION = "Create Microsoft Teams meetings with human approval."


def get_tools() -> list:
    from ai.quickchat.tools import get_current_time

    # Keep the tool registered in the graph so a pending approved call can
    # resume safely even if the token disappeared meanwhile. The middleware
    # below hides it from new model calls while Calendar is disconnected.
    # list_calendar_events is the read-only "what's on my schedule" tool —
    # without it the agent has no way to answer that class of question even
    # though it collects (and has) calendar access; it used to fall back to
    # a wrong "I don't have permission" answer instead of just using it.
    return [get_current_time, list_calendar_events, check_calendar_conflicts, create_teams_meeting]


class CalendarConnectionMiddleware(AgentMiddleware):
    """Hide the create action from the model until Calendar is connected."""

    async def awrap_model_call(self, request: Any, handler: Callable) -> Any:
        from ai.adapters.connectors.calendar import is_calendar_configured

        if is_calendar_configured():
            return await handler(request)
        visible_tools = [
            item
            for item in request.tools
            if (
                item.get("name") if isinstance(item, dict) else getattr(item, "name", "")
            ) != "create_teams_meeting"
        ]
        return await handler(request.override(tools=visible_tools))


def _approval_description(tool_call, _state, _runtime) -> str:
    args = tool_call.get("args") or {}
    return (
        "Confirm creation of this Outlook calendar event with a Microsoft Teams link. "
        "It will be added to the organizer's calendar and Outlook will send invitations.\n\n"
        f"Subject: {args.get('subject', '')}\n"
        f"Start: {args.get('start_datetime', '')}\n"
        f"End: {args.get('end_datetime', '')}\n"
        f"Attendees: {', '.join(args.get('attendee_emails') or []) or 'None'}"
        f"\nAllow calendar conflicts: {'Yes' if args.get('allow_conflicts') else 'No'}"
    )


def build_agent(*, checkpointer=None, thinking: bool = True, effort: str = "medium"):
    from langchain.agents import create_agent
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    from ai.quickchat.agent import CHAT_EFFORT_TO_REASONING
    from ai.quickchat.middleware import build_middleware_stack
    from searchos.config.models import get_model_for, resolve_profile

    reasoning_effort = None
    if resolve_profile("chat").enable_thinking:
        reasoning_effort = CHAT_EFFORT_TO_REASONING.get(effort, "low") if thinking else "none"

    middleware = build_middleware_stack(role="chat")
    middleware.append(CalendarConnectionMiddleware())
    middleware.append(
        HumanInTheLoopMiddleware(
            interrupt_on={
                "create_teams_meeting": {
                    "allowed_decisions": ["approve", "reject"],
                    "description": _approval_description,
                }
            }
        )
    )
    return create_agent(
        model=get_model_for("chat", reasoning_effort=reasoning_effort),
        tools=get_tools(),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        middleware=middleware,
    )
