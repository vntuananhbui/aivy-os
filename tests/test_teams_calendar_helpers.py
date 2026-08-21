from datetime import datetime

from backend.application.connectors.calendar_helpers import find_conflicts, graph_utc, normalize_event


def test_graph_utc_preserves_the_instant() -> None:
    local = datetime.fromisoformat("2026-08-20T09:00:00+07:00")
    assert graph_utc(local) == "2026-08-20T02:00:00Z"


def test_conflicts_ignore_cancelled_free_and_touching_events() -> None:
    events = [
        {
            "id": "overlap",
            "subject": "Busy",
            "start": {"dateTime": "2026-08-20T02:30:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-20T03:30:00Z", "timeZone": "UTC"},
            "showAs": "busy",
        },
        {
            "id": "touching",
            "start": {"dateTime": "2026-08-20T03:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-20T04:00:00Z", "timeZone": "UTC"},
        },
        {
            "id": "free",
            "start": {"dateTime": "2026-08-20T02:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-20T03:00:00Z", "timeZone": "UTC"},
            "showAs": "free",
        },
        {
            "id": "cancelled",
            "start": {"dateTime": "2026-08-20T02:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-20T03:00:00Z", "timeZone": "UTC"},
            "isCancelled": True,
        },
    ]
    conflicts = find_conflicts(
        events,
        datetime.fromisoformat("2026-08-20T09:00:00+07:00"),
        datetime.fromisoformat("2026-08-20T10:00:00+07:00"),
    )
    assert [event["id"] for event in conflicts] == ["overlap"]


def test_normalize_event_extracts_links_and_attendees() -> None:
    event = normalize_event(
        {
            "id": "event-1",
            "subject": "Daily",
            "start": {"dateTime": "2026-08-20T02:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-20T03:00:00Z", "timeZone": "UTC"},
            "isOnlineMeeting": True,
            "onlineMeeting": {"joinUrl": "https://teams/link"},
            "attendees": [{"emailAddress": {"address": "qa@example.com"}}],
        }
    )
    assert event["join_url"] == "https://teams/link"
    assert event["attendees"] == ["qa@example.com"]


def test_normalize_event_finds_teams_link_in_html_body() -> None:
    event = normalize_event(
        {
            "id": "event-2",
            "body": {
                "content": (
                    '<a href="https://teams.microsoft.com/l/meetup-join/abc?x=1&amp;y=2">Join</a>'
                )
            },
        }
    )
    assert event["join_url"] == "https://teams.microsoft.com/l/meetup-join/abc?x=1&y=2"
