import asyncio

import httpx

from connector.microsoft_graph.auth import GraphAuth
from connector.microsoft_graph.client import GraphClientError, TeamsMeetingClient


class StubTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self.handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)


def test_create_calendar_meeting_maps_event_payload(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            201,
            json={
                "id": "event-1",
                "subject": "Project Alpha",
                "onlineMeeting": {"joinUrl": "https://teams/link"},
            },
        )

    transport = StubTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    async def scenario() -> None:
        result = await TeamsMeetingClient(GraphAuth("calendar-token")).create_calendar_meeting(
            transaction_id="action-1",
            subject="Project Alpha",
            start_datetime_utc="2026-08-20T02:00:00Z",
            end_datetime_utc="2026-08-20T03:00:00Z",
            attendee_emails=["qa@example.com"],
        )
        assert result["id"] == "event-1"

    asyncio.run(scenario())
    request = requests[-1]
    assert request.url.path.endswith("/me/events")
    payload = __import__("json").loads(request.content)
    assert payload["isOnlineMeeting"] is True
    assert payload["onlineMeetingProvider"] == "teamsForBusiness"
    assert payload["transactionId"] == "action-1"
    assert payload["attendees"][0]["emailAddress"]["address"] == "qa@example.com"


def test_calendar_view_follows_pagination(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "event-1"}],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/calendarView?$skip=1",
                },
            )
        return httpx.Response(200, json={"value": [{"id": "event-2"}]})

    transport = StubTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    async def scenario() -> None:
        result = await TeamsMeetingClient(GraphAuth("calendar-token")).list_calendar_events(
            start_datetime_utc="2026-08-20T00:00:00Z",
            end_datetime_utc="2026-08-21T00:00:00Z",
        )
        assert [event["id"] for event in result] == ["event-1", "event-2"]

    asyncio.run(scenario())
    assert len(requests) == 2
    assert "startDateTime" in requests[0].url.params
    assert "startDateTime" not in requests[1].url.params
    assert requests[0].headers["prefer"] == 'outlook.timezone="UTC"'


def test_graph_403_has_permission_error(monkeypatch) -> None:
    transport = StubTransport(
        lambda request: httpx.Response(403, json={"error": {"code": "Forbidden"}})
    )
    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    async def scenario() -> None:
        client = TeamsMeetingClient(GraphAuth("opaque-token"))
        try:
            await client.create_calendar_meeting(
                transaction_id="action-1",
                subject="x",
                start_datetime_utc="2026-08-20T02:00:00Z",
                end_datetime_utc="2026-08-20T02:30:00Z",
            )
        except GraphClientError as exc:
            assert exc.code == "MISSING_CALENDAR_PERMISSION"
        else:
            raise AssertionError("expected GraphClientError")

    asyncio.run(scenario())
