"""Pure helpers shared by Calendar read and action tools."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

_TEAMS_JOIN_URL_RE = re.compile(
    r"https://(?:teams\.microsoft\.com|teams\.live\.com)/[^\s<>'\"]+",
    re.IGNORECASE,
)


def parse_aware_datetime(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO 8601 date-time.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset.")
    return parsed


def graph_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_datetime(event: dict, key: str) -> datetime | None:
    raw = (event.get(key) or {}).get("dateTime")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    # Calendar requests use Prefer: outlook.timezone="UTC". Graph sometimes
    # omits the suffix while still labeling the DateTimeTimeZone as UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def find_conflicts(events: list[dict], start: datetime, end: datetime) -> list[dict]:
    conflicts = []
    for event in events:
        if event.get("isCancelled") or str(event.get("showAs") or "").casefold() == "free":
            continue
        event_start = event_datetime(event, "start")
        event_end = event_datetime(event, "end")
        if event_start is None or event_end is None:
            continue
        if event_start < end.astimezone(UTC) and event_end > start.astimezone(UTC):
            conflicts.append(
                {
                    "id": event.get("id", ""),
                    "subject": event.get("subject") or "(No title)",
                    "start_datetime": event_start.isoformat(),
                    "end_datetime": event_end.isoformat(),
                    "is_all_day": bool(event.get("isAllDay")),
                    "event_url": event.get("webLink") or "",
                }
            )
    return conflicts


def normalize_event(event: dict) -> dict:
    start = event_datetime(event, "start")
    end = event_datetime(event, "end")
    online = event.get("onlineMeeting") or {}
    join_url = online.get("joinUrl") or event.get("onlineMeetingUrl") or ""
    if not join_url:
        body = html.unescape(str((event.get("body") or {}).get("content") or ""))
        match = _TEAMS_JOIN_URL_RE.search(body)
        join_url = match.group(0) if match else ""
    return {
        "id": event.get("id", ""),
        "subject": event.get("subject") or "(No title)",
        "start_datetime": start.isoformat() if start else "",
        "end_datetime": end.isoformat() if end else "",
        "is_all_day": bool(event.get("isAllDay")),
        "is_cancelled": bool(event.get("isCancelled")),
        "show_as": event.get("showAs") or "",
        "is_online_meeting": bool(event.get("isOnlineMeeting")),
        "join_url": join_url,
        "event_url": event.get("webLink") or "",
        "location": (event.get("location") or {}).get("displayName") or "",
        "organizer": ((event.get("organizer") or {}).get("emailAddress") or {}).get("address") or "",
        "attendees": [
            (attendee.get("emailAddress") or {}).get("address")
            for attendee in event.get("attendees") or []
            if (attendee.get("emailAddress") or {}).get("address")
        ],
        "series_master_id": event.get("seriesMasterId") or "",
        "type": event.get("type") or "",
    }
