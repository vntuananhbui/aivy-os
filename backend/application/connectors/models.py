"""Connector domain DTOs shared by services and repository ports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharePointSelectionItem:
    id: str
    name: str
    path: str = ""
    web_url: str = ""
    is_folder: bool = False


@dataclass(frozen=True)
class JiraCredentialData:
    site_url: str
    auth_mode: str
    email: str = ""
    api_token: str = ""
    personal_access_token: str = ""
    access_token: str = ""
    expires_at: float = 0.0
    cloud_id: str = ""
