"""In-process holder for the Jira credential (API token or PAT).

Deliberately NOT persisted anywhere (not ``.env``, not ``web_settings.json``)
— same rationale as ``connector.sharepoint.token_store``, kept here instead
of shared because the credential shape differs (site_url/auth_mode/email +
one of api_token/personal_access_token vs a single bearer token). Lost on
process restart — the user reconnects, same as SharePoint's re-paste flow.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JiraCredential:
    site_url: str
    auth_mode: str  # "cloud" | "server" | "oauth"
    email: str = ""
    api_token: str = ""
    personal_access_token: str = ""
    # "oauth" mode only — short-lived (~1h) 3LO access token, no refresh_token
    # stored/used (see connector.jira.auth's no-silent-refresh rationale).
    access_token: str = ""
    expires_at: float | None = None
    cloud_id: str = ""


_credential: JiraCredential | None = None


def set_credential(credential: JiraCredential) -> None:
    global _credential
    _credential = credential


def get_credential() -> JiraCredential | None:
    return _credential


def clear_credential() -> None:
    global _credential
    _credential = None
