"""Microsoft Graph client for Outlook calendar-backed Teams meetings."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from backend.infrastructure.connectors.microsoft_graph.auth import GraphAuth

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClientError(Exception):
    def __init__(self, message: str, *, code: str = "GRAPH_ERROR", status_code: int = 0):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _error_for_response(
    response: httpx.Response, *, permission_hint: str = "Calendars.ReadWrite"
) -> GraphClientError:
    status = response.status_code
    graph_code = ""
    try:
        graph_code = str((response.json().get("error") or {}).get("code") or "")
    except Exception:
        pass
    if status == 401:
        return GraphClientError(
            "Microsoft session is no longer valid — sign in again.",
            code="TOKEN_INVALID",
            status_code=status,
        )
    if status == 403:
        return GraphClientError(
            "Microsoft Graph denied the action. Ensure the app has delegated "
            f"{permission_hint} permission and tenant consent, then sign in again.",
            code={
                "Calendars.ReadWrite": "MISSING_CALENDAR_PERMISSION",
                "Calendars.Read": "MISSING_CALENDAR_PERMISSION",
            }.get(permission_hint, "GRAPH_PERMISSION_DENIED"),
            status_code=status,
        )
    if status == 429:
        return GraphClientError(
            "Microsoft Graph is rate limiting meeting creation. Try again later.",
            code="GRAPH_RATE_LIMITED",
            status_code=status,
        )
    if status >= 500:
        return GraphClientError(
            "Microsoft Graph is temporarily unavailable.",
            code="GRAPH_UNAVAILABLE",
            status_code=status,
        )
    return GraphClientError(
        f"Microsoft Graph rejected the request ({graph_code or status}).",
        code=graph_code or "GRAPH_REQUEST_REJECTED",
        status_code=status,
    )


class TeamsMeetingClient:
    def __init__(self, auth: GraphAuth, *, timeout: float = 20.0):
        self._auth = auth
        self._timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        *,
        permission_hint: str = "Calendars.ReadWrite",
        prefer_timezone: str | None = None,
        **kwargs,
    ) -> dict:
        token = await self._auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if prefer_timezone:
            headers["Prefer"] = f'outlook.timezone="{prefer_timezone}"'
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                url = path if path.startswith("https://graph.microsoft.com/") else f"{GRAPH_BASE}{path}"
                response = await client.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            is_write = method.upper() in {"POST", "PATCH", "DELETE"}
            raise GraphClientError(
                (
                    "Microsoft Graph timed out after a write request; calendar state is unknown."
                    if is_write
                    else "Microsoft Graph timed out while reading calendar data."
                ),
                code="GRAPH_WRITE_TIMEOUT" if is_write else "GRAPH_TIMEOUT",
            ) from exc
        if response.status_code >= 400:
            raise _error_for_response(response, permission_hint=permission_hint)
        try:
            return response.json()
        except ValueError as exc:
            raise GraphClientError(
                "Microsoft Graph returned an invalid response.", code="INVALID_GRAPH_RESPONSE"
            ) from exc

    async def create_calendar_meeting(
        self,
        *,
        transaction_id: str,
        subject: str,
        start_datetime_utc: str,
        end_datetime_utc: str,
        attendee_emails: list[str] | None = None,
    ) -> dict:
        """Create an Outlook event that asks Graph to provision a Teams meeting."""
        body = {
            "subject": subject,
            "start": {"dateTime": start_datetime_utc, "timeZone": "UTC"},
            "end": {"dateTime": end_datetime_utc, "timeZone": "UTC"},
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendee_emails or []
            ],
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
            "transactionId": transaction_id,
        }
        data = await self._request(
            "POST", "/me/events", permission_hint="Calendars.ReadWrite", json=body
        )
        if not data.get("id"):
            raise GraphClientError(
                "Microsoft Graph response did not include a calendar event ID.",
                code="INVALID_GRAPH_RESPONSE",
            )
        return data

    async def get_calendar_event(self, event_id: str) -> dict:
        return await self._request(
            "GET",
            f"/me/events/{quote(event_id, safe='')}",
            permission_hint="Calendars.Read",
            prefer_timezone="UTC",
            params={
                "$select": (
                    "id,subject,start,end,isAllDay,isCancelled,showAs,location,organizer,"
                    "attendees,isOnlineMeeting,onlineMeeting,onlineMeetingUrl,body,webLink,"
                    "lastModifiedDateTime"
                )
            },
        )

    async def list_calendar_events(
        self,
        *,
        start_datetime_utc: str,
        end_datetime_utc: str,
        max_results: int = 200,
    ) -> list[dict]:
        """List expanded calendar occurrences in a half-open time range."""
        path = "/me/calendarView"
        params: dict | None = {
            "startDateTime": start_datetime_utc,
            "endDateTime": end_datetime_utc,
            "$orderby": "start/dateTime",
            "$top": min(max(max_results, 1), 100),
            "$select": (
                "id,subject,start,end,isAllDay,isCancelled,showAs,location,organizer,"
                "attendees,isOnlineMeeting,onlineMeeting,webLink,seriesMasterId,type"
            ),
        }
        events: list[dict] = []
        while path and len(events) < max_results:
            page = await self._request(
                "GET",
                path,
                permission_hint="Calendars.Read",
                prefer_timezone="UTC",
                params=params,
            )
            events.extend(page.get("value") or [])
            next_link = page.get("@odata.nextLink")
            path = str(next_link) if next_link else ""
            params = None
        return events[:max_results]
