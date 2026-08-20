"""LangChain adapters for read-only Calendar queries and approved meeting creation."""

from __future__ import annotations

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from backend.application.connectors.calendar_access import validate_meeting_args
from backend.bootstrap.connectors import calendar_access_service, connector_capability_reader


def is_calendar_configured() -> bool:
    return connector_capability_reader.is_connected("calendar")


@tool
async def list_calendar_events(
    start_datetime: str,
    end_datetime: str,
    online_only: bool = False,
) -> dict:
    """Read Outlook calendar events in a timezone-aware date range.

    Always use this tool for questions about the user's schedule, existing
    meetings, availability, or Teams links. It expands recurring occurrences.
    This is read-only and does not require approval.

    Args:
        start_datetime: Inclusive ISO 8601 range start with timezone offset.
        end_datetime: Exclusive ISO 8601 range end with timezone offset.
        online_only: True only when explicitly asking for Teams/online meetings.
    """
    return await calendar_access_service.list_events(
        start_datetime,
        end_datetime,
        online_only=online_only,
    )


@tool
async def check_calendar_conflicts(start_datetime: str, end_datetime: str) -> dict:
    """Check Outlook calendar conflicts before proposing meeting creation.

    Call after start/end are complete and before ``create_teams_meeting``.
    Cancelled and free events are not conflicts. This action is read-only.

    Args:
        start_datetime: ISO 8601 start including timezone offset.
        end_datetime: ISO 8601 end including timezone offset.
    """
    return await calendar_access_service.check_conflicts(start_datetime, end_datetime)


@tool
async def create_teams_meeting(
    subject: str,
    start_datetime: str,
    end_datetime: str,
    runtime: ToolRuntime,
    attendee_emails: list[str] | None = None,
    allow_conflicts: bool = False,
) -> dict:
    """Create an Outlook calendar event with a Microsoft Teams join link.

    Use only when all arguments are complete and ``check_calendar_conflicts``
    was called. This creates an event and sends invitations after human approval.

    Args:
        subject: Meeting title.
        start_datetime: ISO 8601 start including timezone offset.
        end_datetime: ISO 8601 end including timezone offset.
        attendee_emails: Optional Microsoft work/school account emails.
        allow_conflicts: True only after explicit consent to ignore conflicts.
    """
    tool_call_id = runtime.tool_call_id
    if not tool_call_id:
        raise RuntimeError("Meeting action is missing its tool call ID.")
    thread_id = str((runtime.config.get("configurable") or {}).get("thread_id") or "")
    if not thread_id:
        raise RuntimeError("Meeting action is missing its conversation thread ID.")
    return await calendar_access_service.create_meeting(
        operation_id=f"searchos:{thread_id}:{tool_call_id}",
        subject=subject,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        attendee_emails=attendee_emails,
        allow_conflicts=allow_conflicts,
    )


__all__ = [
    "check_calendar_conflicts",
    "create_teams_meeting",
    "is_calendar_configured",
    "list_calendar_events",
    "validate_meeting_args",
]
