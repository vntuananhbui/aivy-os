"""Outlook Calendar and Teams meeting use cases independent from agent tools."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from backend.application.connectors.repositories import TeamsConnectionRepository
from connector.microsoft_graph import GraphAuth, GraphClientError, TeamsMeetingClient
from connector.teams.calendar import (
    find_conflicts,
    graph_utc,
    normalize_event,
    parse_aware_datetime,
)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_meeting_args(
    subject: str,
    start_datetime: str,
    end_datetime: str,
    attendee_emails: list[str] | None,
) -> tuple[str, datetime, datetime, list[str]]:
    clean_subject = " ".join(subject.split())
    if not clean_subject:
        raise ValueError("Meeting subject is required.")
    start = parse_aware_datetime(start_datetime, field="Meeting start")
    end = parse_aware_datetime(end_datetime, field="Meeting end")
    if end <= start:
        raise ValueError("Meeting end must be after its start.")

    emails: list[str] = []
    seen: set[str] = set()
    for raw in attendee_emails or []:
        email = raw.strip().casefold()
        if not _EMAIL_RE.fullmatch(email):
            raise ValueError(f"Invalid attendee email: {raw}")
        if email not in seen:
            emails.append(email)
            seen.add(email)
    return clean_subject, start, end, emails


def _graph_error_result(exc: GraphClientError, **extra: Any) -> dict[str, Any]:
    status = (
        "authentication_required"
        if exc.code == "TOKEN_INVALID"
        else "permission_required"
        if exc.code == "MISSING_CALENDAR_PERMISSION"
        else "status_unknown"
        if exc.code == "GRAPH_WRITE_TIMEOUT"
        else "failed"
    )
    return {
        "success": False,
        "status": status,
        "error_code": exc.code,
        "message": str(exc),
        "status_code": exc.status_code,
        **extra,
    }


class CalendarAccessService:
    def __init__(
        self,
        repository: TeamsConnectionRepository,
        *,
        client_factory: Callable[[str], TeamsMeetingClient] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[Any], datetime] = datetime.now,
    ) -> None:
        self._repository = repository
        self._client_factory = client_factory or (
            lambda token: TeamsMeetingClient(GraphAuth(token))
        )
        self._sleep = sleep
        self._now = now

    async def _client(self) -> TeamsMeetingClient | None:
        status = await self._repository.status()
        token = await self._repository.get_access_token()
        if not status or not status.get("connected") or not token:
            return None
        return self._client_factory(token)

    async def list_events(
        self,
        start_datetime: str,
        end_datetime: str,
        *,
        online_only: bool = False,
    ) -> dict[str, Any]:
        start = parse_aware_datetime(start_datetime, field="start_datetime")
        end = parse_aware_datetime(end_datetime, field="end_datetime")
        if end <= start:
            raise ValueError("end_datetime must be after start_datetime.")
        client = await self._client()
        if client is None:
            return {
                "success": False,
                "status": "authentication_required",
                "message": "Connect Microsoft Teams/Calendar before reading calendar events.",
                "events": [],
            }
        try:
            raw = await client.list_calendar_events(
                start_datetime_utc=graph_utc(start),
                end_datetime_utc=graph_utc(end),
            )
        except GraphClientError as exc:
            return _graph_error_result(exc, events=[])
        events = [normalize_event(event) for event in raw if not event.get("isCancelled")]
        if online_only:
            events = [event for event in events if event["is_online_meeting"]]
        return {
            "success": True,
            "status": "ok",
            "range_start": start.isoformat(),
            "range_end": end.isoformat(),
            "events": events,
        }

    async def check_conflicts(self, start_datetime: str, end_datetime: str) -> dict[str, Any]:
        _, start, end, _ = validate_meeting_args(
            "Conflict check", start_datetime, end_datetime, None
        )
        client = await self._client()
        if client is None:
            return {
                "success": False,
                "status": "authentication_required",
                "message": "Connect Microsoft Teams/Calendar before checking the calendar.",
                "conflicts": [],
            }
        try:
            events = await client.list_calendar_events(
                start_datetime_utc=graph_utc(start),
                end_datetime_utc=graph_utc(end),
            )
        except GraphClientError as exc:
            return _graph_error_result(exc, conflicts=[])
        conflicts = find_conflicts(events, start, end)
        return {
            "success": True,
            "status": "conflict" if conflicts else "available",
            "conflicts": conflicts,
        }

    async def create_meeting(
        self,
        *,
        operation_id: str,
        subject: str,
        start_datetime: str,
        end_datetime: str,
        attendee_emails: list[str] | None = None,
        allow_conflicts: bool = False,
    ) -> dict[str, Any]:
        clean_subject, start, end, emails = validate_meeting_args(
            subject, start_datetime, end_datetime, attendee_emails
        )
        if start <= self._now(start.tzinfo):
            return {
                "success": False,
                "status": "failed",
                "error_code": "MEETING_START_IN_PAST",
                "error": "Meeting start must be in the future. Ask the user for a new start time.",
                "calendar_event_created": False,
            }
        if not operation_id:
            raise ValueError("Meeting operation_id is required for idempotency.")
        client = await self._client()
        if client is None:
            return {
                "success": False,
                "status": "authentication_required",
                "error_code": "CALENDAR_NOT_CONNECTED",
                "message": "Microsoft Teams/Calendar is not connected. Connect it in Settings.",
                "calendar_event_created": False,
            }
        try:
            existing = await client.list_calendar_events(
                start_datetime_utc=graph_utc(start),
                end_datetime_utc=graph_utc(end),
            )
            conflicts = find_conflicts(existing, start, end)
            if conflicts and not allow_conflicts:
                return {
                    "success": False,
                    "status": "conflict",
                    "error_code": "SCHEDULE_CONFLICT",
                    "message": "The requested time overlaps existing calendar events.",
                    "conflicts": conflicts,
                    "calendar_event_created": False,
                }
            event = await client.create_calendar_meeting(
                transaction_id=operation_id,
                subject=clean_subject,
                start_datetime_utc=graph_utc(start),
                end_datetime_utc=graph_utc(end),
                attendee_emails=emails,
            )
        except GraphClientError as exc:
            return _graph_error_result(exc, calendar_event_created=False)

        normalized = normalize_event(event)
        for delay_seconds in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
            if normalized["join_url"]:
                break
            if delay_seconds:
                await self._sleep(delay_seconds)
            try:
                normalized = normalize_event(await client.get_calendar_event(event["id"]))
            except GraphClientError:
                break
        return {
            "success": True,
            "status": "created" if normalized["join_url"] else "link_pending",
            "event_id": normalized["id"],
            "subject": normalized["subject"] or clean_subject,
            "start_datetime": normalized["start_datetime"] or start.isoformat(),
            "end_datetime": normalized["end_datetime"] or end.isoformat(),
            "attendees": emails,
            "join_url": normalized["join_url"],
            "event_url": normalized["event_url"],
            "calendar_event_created": True,
        }
