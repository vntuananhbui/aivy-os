"""Jira OAuth 2.0 (3LO) application service."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from loguru import logger

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.jira import JiraConnectorService
from backend.application.connectors.oauth_state import OAuthStateRepository

JIRA_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
JIRA_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
JIRA_OAUTH_SCOPES = "read:jira-work write:jira-work read:jira-user"
OAUTH_STATE_TTL = 300


@dataclass(frozen=True)
class JiraOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def from_env(cls) -> "JiraOAuthConfig":
        return cls(
            client_id=os.environ.get("JIRA_CLIENT_ID", ""),
            client_secret=os.environ.get("JIRA_SECRET", ""),
            redirect_uri=os.environ.get("JIRA_REDIRECT_URI", ""),
        )

    def validate(self) -> None:
        if not (self.client_id and self.client_secret and self.redirect_uri):
            raise ConnectorServiceError(
                "oauth_not_configured",
                "Jira OAuth is not configured on the server — missing "
                "JIRA_CLIENT_ID / JIRA_SECRET / JIRA_REDIRECT_URI.",
            )


@dataclass(frozen=True)
class JiraOAuthConnection:
    site_url: str
    cloud_id: str


class JiraOAuthService:
    def __init__(
        self,
        *,
        state_repository: OAuthStateRepository,
        jira_service: JiraConnectorService,
    ) -> None:
        self._states = state_repository
        self._jira = jira_service

    async def authorization_url(self) -> str:
        config = JiraOAuthConfig.from_env()
        config.validate()
        state = await self._states.create()
        params = {
            "audience": "api.atlassian.com",
            "client_id": config.client_id,
            "scope": JIRA_OAUTH_SCOPES,
            "redirect_uri": config.redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        return f"{JIRA_AUTHORIZE_URL}?{urlencode(params)}"

    async def complete(self, *, state: str, code: str) -> JiraOAuthConnection:
        if not state or not await self._states.consume(state):
            raise ConnectorServiceError(
                "oauth_state_invalid",
                "This login link expired or was already used.",
            )
        if not code:
            raise ConnectorServiceError(
                "oauth_code_missing",
                "Jira did not return an authorization code.",
            )

        config = JiraOAuthConfig.from_env()
        config.validate()
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                JIRA_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "redirect_uri": config.redirect_uri,
                },
            )
            if token_response.status_code >= 400:
                data = token_response.json() if token_response.content else {}
                logger.warning(
                    "Jira OAuth token exchange failed: {} {}",
                    token_response.status_code,
                    data.get("error") or data.get("error_description"),
                )
                raise ConnectorServiceError(
                    "oauth_exchange_failed",
                    "Could not exchange the Jira login code for a token.",
                    retryable=True,
                )
            token_data = token_response.json()
            access_token = token_data["access_token"]
            expires_at = time.time() + token_data.get("expires_in", 3600) - 30

            resources_response = await client.get(
                JIRA_RESOURCES_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            if resources_response.status_code >= 400:
                logger.warning(
                    "Jira OAuth accessible-resources failed: {}",
                    resources_response.status_code,
                )
                raise ConnectorServiceError(
                    "oauth_resources_failed",
                    "Could not list the Jira sites this account can access.",
                    retryable=True,
                )
            resources = resources_response.json()

        if not resources:
            raise ConnectorServiceError(
                "oauth_no_resources",
                "This Atlassian account has no accessible Jira site.",
            )
        resource = resources[0]
        cloud_id = resource.get("id", "")
        site_url = resource.get("url", "")
        await self._jira.save_oauth_connection(
            site_url=site_url,
            cloud_id=cloud_id,
            access_token=access_token,
            expires_at=expires_at,
        )
        return JiraOAuthConnection(site_url=site_url, cloud_id=cloud_id)

