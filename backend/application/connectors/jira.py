"""Jira connection, selection and lifecycle use cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.models import JiraCredentialData
from backend.application.connectors.repositories import (
    ConnectorCacheRepository,
    JiraConnectionRepository,
)
from backend.application.connectors.provider_ports import JIRA_SOURCE, JiraProviderFactory


@dataclass(frozen=True)
class JiraConnectRequest:
    site_url: str
    auth_mode: str
    email: str = ""
    api_token: str = ""
    personal_access_token: str = ""
    project_keys: list[str] = field(default_factory=list)


class JiraConnectorService:
    def __init__(
        self,
        *,
        repository: JiraConnectionRepository,
        cache_repository: ConnectorCacheRepository,
        connector_factory: JiraProviderFactory,
    ) -> None:
        self._repository = repository
        self._cache = cache_repository
        self._connector_factory = connector_factory

    async def status(self) -> dict | None:
        return await self._repository.status()

    async def connect(self, request: JiraConnectRequest) -> dict:
        email = request.email.strip()
        api_token = request.api_token.strip()
        personal_access_token = request.personal_access_token.strip()
        if request.auth_mode == "cloud" and not (email and api_token):
            raise ConnectorServiceError(
                "validation_error", "Jira Cloud requires both email and api_token."
            )
        if request.auth_mode == "server" and not personal_access_token:
            raise ConnectorServiceError(
                "validation_error",
                "Jira Server/DC requires a personal_access_token.",
            )

        site_url = request.site_url.strip()
        connector = self._connector_factory(
            site_url,
            request.auth_mode,
            email=email,
            api_token=api_token,
            personal_access_token=personal_access_token,
        )
        try:
            await connector.connect()
        except Exception as exc:
            raise ConnectorServiceError(
                "connection_failed",
                f"Could not connect to Jira: {exc}",
                retryable=True,
            ) from exc

        await self._repository.save_connected(
            JiraCredentialData(
                site_url=site_url,
                auth_mode=request.auth_mode,
                email=email,
                api_token=api_token,
                personal_access_token=personal_access_token,
            ),
            project_keys=request.project_keys,
        )
        return (await self.status()) or {"connected": True}

    async def update_selection(self, project_keys: list[str]) -> dict:
        if await self._repository.status() is None:
            raise ConnectorServiceError(
                "authentication_required",
                "Jira is not connected — connect it first.",
            )
        await self._repository.save_selection(project_keys)
        return (await self.status()) or {"connected": False}

    async def save_oauth_connection(
        self,
        *,
        site_url: str,
        cloud_id: str,
        access_token: str,
        expires_at: float,
    ) -> dict:
        await self._repository.save_connected(
            JiraCredentialData(
                site_url=site_url,
                auth_mode="oauth",
                access_token=access_token,
                expires_at=expires_at,
                cloud_id=cloud_id,
            ),
            preserve_project_keys=True,
        )
        return (await self.status()) or {"connected": True}

    async def disconnect(self) -> None:
        await self._repository.clear()
        await self._cache.purge_source(JIRA_SOURCE)
