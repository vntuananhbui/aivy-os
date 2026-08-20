"""Jira credential holder — supports the three auth shapes Jira ships:

- **Cloud (API token)**: Basic Auth with `email` + `api_token` (long-lived,
  no exp claim to decode — unlike SharePoint's short-lived pasted Graph
  token).
- **Server/Data Center**: Bearer `personal_access_token`, no email.
- **Cloud (OAuth 2.0 3LO — "Login with Jira")**: Bearer `access_token`
  routed through `api.atlassian.com/ex/jira/{cloud_id}/...` instead of the
  site's own REST API. Short-lived (~1h) — deliberately **not** refreshed
  here (no `refresh_token` stored, no `offline_access` scope requested):
  `auth_header()` raises past `expires_at` so callers surface a clear
  "reconnect" message instead of a raw 401, same behavior as
  ``SharePointAuth`` when its pasted token expires.
"""

from __future__ import annotations

import base64
import time


class JiraAuthError(Exception):
    """Raised when the stored credential is missing, malformed, or expired."""


class JiraAuth:
    def __init__(
        self,
        site_url: str,
        auth_mode: str,
        *,
        email: str = "",
        api_token: str = "",
        personal_access_token: str = "",
        access_token: str = "",
        expires_at: float | None = None,
        cloud_id: str = "",
    ):
        if not site_url:
            raise JiraAuthError("No Jira site URL provided.")
        if auth_mode not in ("cloud", "server", "oauth"):
            raise JiraAuthError(f"Unknown Jira auth_mode: {auth_mode!r}")
        if auth_mode == "cloud" and not (email and api_token):
            raise JiraAuthError("Jira Cloud requires both email and api_token.")
        if auth_mode == "server" and not personal_access_token:
            raise JiraAuthError("Jira Server/DC requires a personal_access_token.")
        if auth_mode == "oauth" and not (access_token and cloud_id):
            raise JiraAuthError("Jira OAuth requires both access_token and cloud_id.")

        self.site_url = site_url.rstrip("/")
        self.auth_mode = auth_mode
        self._email = email
        self._api_token = api_token
        self._personal_access_token = personal_access_token
        self._access_token = access_token
        self._expires_at = expires_at
        self._cloud_id = cloud_id

    @property
    def api_prefix(self) -> str:
        if self.auth_mode == "oauth":
            return f"/ex/jira/{self._cloud_id}/rest/api/3"
        return "/rest/api/3" if self.auth_mode == "cloud" else "/rest/api/2"

    @property
    def base_url(self) -> str:
        return "https://api.atlassian.com" if self.auth_mode == "oauth" else self.site_url

    def auth_header(self) -> str:
        if self.auth_mode == "cloud":
            raw = f"{self._email}:{self._api_token}".encode()
            return f"Basic {base64.b64encode(raw).decode()}"
        if self.auth_mode == "server":
            return f"Bearer {self._personal_access_token}"
        if self._expires_at is not None and time.time() >= self._expires_at:
            raise JiraAuthError(
                "Jira OAuth access token has expired — click 'Login with Jira' again."
            )
        return f"Bearer {self._access_token}"
