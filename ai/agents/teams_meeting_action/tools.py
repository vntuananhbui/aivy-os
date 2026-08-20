"""Teams meeting agent tool binding over canonical Calendar adapters."""

from ai.adapters.connectors.calendar import (
    check_calendar_conflicts,
    create_teams_meeting,
    validate_meeting_args,
)

__all__ = [
    "check_calendar_conflicts",
    "create_teams_meeting",
    "validate_meeting_args",
]
