import pytest

from ai.agents.teams_meeting_action import agent
from ai.agents.teams_meeting_action import tools
from ai.agents.teams_meeting_action.tools import validate_meeting_args
from agents import teams_meeting_action as legacy_teams_meeting_action
from ai.adapters.connectors.calendar import (
    check_calendar_conflicts,
    create_teams_meeting,
)


def test_meeting_tools_are_compatibility_reexports() -> None:
    assert tools.check_calendar_conflicts is check_calendar_conflicts
    assert tools.create_teams_meeting is create_teams_meeting
    assert not hasattr(tools, "token_store")


def test_create_action_stays_registered_for_safe_resume() -> None:
    assert [item.name for item in agent.get_tools()] == [
        "get_current_time",
        "list_calendar_events",
        "check_calendar_conflicts",
        "create_teams_meeting",
    ]


def test_legacy_agent_package_reexports_canonical_agent() -> None:
    assert legacy_teams_meeting_action.build_agent is agent.build_agent
    assert legacy_teams_meeting_action.get_tools is agent.get_tools

def test_validate_meeting_args_normalizes_and_deduplicates() -> None:
    subject, start, end, emails = validate_meeting_args(
        "  Project   Alpha ",
        "2026-08-20T09:00:00+07:00",
        "2026-08-20T09:45:00+07:00",
        ["QA@example.com", "qa@example.com"],
    )
    assert subject == "Project Alpha"
    assert end > start
    assert emails == ["qa@example.com"]


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("2026-08-20T09:00:00", "2026-08-20T09:45:00+07:00", "start"),
        ("2026-08-20T09:00:00+07:00", "2026-08-20T09:45:00", "end"),
        ("2026-08-20T09:45:00+07:00", "2026-08-20T09:00:00+07:00", "after"),
    ],
)
def test_validate_meeting_args_rejects_invalid_times(start, end, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_meeting_args("Subject", start, end, None)


def test_validate_meeting_args_rejects_bad_email() -> None:
    with pytest.raises(ValueError, match="Invalid attendee email"):
        validate_meeting_args(
            "Subject",
            "2026-08-20T09:00:00+07:00",
            "2026-08-20T09:45:00+07:00",
            ["not-an-email"],
        )
