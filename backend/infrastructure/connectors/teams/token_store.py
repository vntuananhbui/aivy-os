"""Process-local delegated Graph token holder, dedicated to Teams.

Deliberately a SEPARATE in-memory store from ``connector.sharepoint`` (which
is a facade over ``connector.microsoft_graph.token_store``) — the two used to
share one token/one Microsoft login on the theory that a single sign-in could
cover both, but SharePoint (Files.Read/Sites.Read.All) and Teams/Calendar
(Calendars.ReadWrite) need different Graph scopes, and
requesting them together via ``.default`` silently dropped Files.* if it
wasn't already consented. Two logins, two tokens, two scope requests — see
``web/frontend/src/lib/msal.ts``'s ``getTeamsAccessToken`` /
``getSharePointAccessToken``.

Same non-persistence rationale as ``connector.sharepoint.token_store``: never
written to disk, lost on process restart, the user just signs in again.
"""

from __future__ import annotations

_token: str | None = None


def set_token(token: str) -> None:
    global _token
    _token = token.strip()


def get_token() -> str | None:
    return _token


def clear_token() -> None:
    global _token
    _token = None
