import asyncio
from datetime import datetime

from backend.application.connectors.calendar_access import CalendarAccessService


class TeamsRepository:
    def __init__(self, token="teams-token"):
        self.token = token

    async def status(self):
        return {"connected": bool(self.token)}

    async def get_access_token(self):
        return self.token


class CalendarClient:
    def __init__(self, events=None, created=None, refreshed=None):
        self.events = events or []
        self.created = created or {}
        self.refreshed = refreshed or self.created
        self.create_calls = []

    async def list_calendar_events(self, **kwargs):
        return self.events

    async def create_calendar_meeting(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.created

    async def get_calendar_event(self, event_id):
        return self.refreshed


def _event(*, event_id="event-1", join_url=""):
    return {
        "id": event_id,
        "subject": "Planning",
        "start": {"dateTime": "2026-08-20T04:00:00Z"},
        "end": {"dateTime": "2026-08-20T05:00:00Z"},
        "showAs": "busy",
        "isOnlineMeeting": True,
        "onlineMeeting": {"joinUrl": join_url} if join_url else None,
        "webLink": "https://outlook/event-1",
    }


def test_calendar_service_reports_authentication_required_without_token() -> None:
    service = CalendarAccessService(TeamsRepository(token=""))

    result = asyncio.run(service.check_conflicts(
        "2026-08-20T11:00:00+07:00", "2026-08-20T12:00:00+07:00"
    ))

    assert result["status"] == "authentication_required"


def test_calendar_service_rechecks_conflict_before_approved_write() -> None:
    client = CalendarClient(events=[_event()])
    service = CalendarAccessService(
        TeamsRepository(),
        client_factory=lambda _: client,
        now=lambda _tz: datetime.fromisoformat("2026-08-20T09:00:00+07:00"),
    )

    result = asyncio.run(service.create_meeting(
        operation_id="searchos:thread:call",
        subject="Planning",
        start_datetime="2026-08-20T11:00:00+07:00",
        end_datetime="2026-08-20T12:00:00+07:00",
    ))

    assert result["status"] == "conflict"
    assert result["calendar_event_created"] is False
    assert client.create_calls == []


def test_calendar_service_uses_operation_id_and_returns_join_url() -> None:
    client = CalendarClient(
        created=_event(),
        refreshed=_event(join_url="https://teams.microsoft.com/l/meetup-join/abc"),
    )

    async def no_sleep(_seconds):
        return None

    service = CalendarAccessService(
        TeamsRepository(),
        client_factory=lambda _: client,
        sleep=no_sleep,
        now=lambda _tz: datetime.fromisoformat("2026-08-20T09:00:00+07:00"),
    )
    result = asyncio.run(service.create_meeting(
        operation_id="searchos:thread:call",
        subject="  Planning  ",
        start_datetime="2026-08-20T11:00:00+07:00",
        end_datetime="2026-08-20T12:00:00+07:00",
        attendee_emails=["QA@example.com", "qa@example.com"],
    ))

    assert result["status"] == "created"
    assert result["join_url"].startswith("https://teams.microsoft.com/")
    assert result["attendees"] == ["qa@example.com"]
    assert client.create_calls[0]["transaction_id"] == "searchos:thread:call"
