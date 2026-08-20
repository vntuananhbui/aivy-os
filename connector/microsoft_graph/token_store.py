"""Process-local delegated Graph token holder — SharePoint's dedicated store.

The existing product obtains a short-lived token in the browser and sends it to
the backend. It is intentionally not persisted to disk.

Historically SharePoint and Teams shared this one store on the theory that a
single Microsoft login could cover both — dropped: they need different Graph
scopes (Files.Read/Sites.Read.All vs Calendars.ReadWrite), and requesting both
via one ``.default`` login silently
omitted Files.* when it wasn't already consented, breaking SharePoint. Teams
now has its own store (``connector.teams.token_store``) and its own login
scope request — see ``web/frontend/src/lib/msal.ts``.
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
