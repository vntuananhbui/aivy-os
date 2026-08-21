"""SharePoint/OneDrive connection and browsing use cases."""

from __future__ import annotations

from loguru import logger

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.models import SharePointSelectionItem
from backend.application.connectors.repositories import (
    ConnectorCacheRepository,
    SharePointConnectionRepository,
    TeamsConnectionRepository,
)
from backend.application.connectors.provider_ports import (
    SHAREPOINT_SOURCE,
    SharePointProvider,
    SharePointProviderFactory,
    TokenInspector,
)


class SharePointConnectorService:
    def __init__(
        self,
        *,
        repository: SharePointConnectionRepository,
        teams_repository: TeamsConnectionRepository,
        cache_repository: ConnectorCacheRepository,
        connector_factory: SharePointProviderFactory,
        token_inspector: TokenInspector,
    ) -> None:
        self._repository = repository
        self._teams_repository = teams_repository
        self._cache = cache_repository
        self._connector_factory = connector_factory
        self._token_inspector = token_inspector

    async def status(self) -> dict | None:
        return await self._repository.status()

    async def _connector(self) -> SharePointProvider:
        token = await self._repository.get_access_token()
        if not token:
            raise ConnectorServiceError(
                "authentication_required",
                "SharePoint is not connected — paste an access token first.",
            )
        return self._connector_factory(token)

    async def connect(self, access_token: str) -> dict:
        token = access_token.strip()
        claims, scopes = self._token_inspector(token)
        logger.info(
            "SharePoint login: token_type={} tenant_id={} client_id={} expires_at={} "
            "delegated_scopes={}",
            "delegated" if claims.get("scp") else "app-only-or-unknown",
            claims.get("tid", "unknown"),
            claims.get("appid") or claims.get("azp", "unknown"),
            claims.get("exp", "unknown"),
            list(scopes),
        )
        connector = self._connector_factory(token)
        try:
            await connector.connect()
        except Exception as exc:
            raise ConnectorServiceError(
                "connection_failed",
                f"Could not connect to SharePoint: {exc}",
                retryable=True,
            ) from exc

        await self._repository.save_connected(token)
        calendar_capable = "Calendars.ReadWrite" in set(scopes)
        if calendar_capable:
            await self._teams_repository.save_connected(token)
            logger.info(
                "SharePoint login token also has Calendars.ReadWrite; "
                "activated Teams/Calendar connector from the same capable token"
            )

        return (await self.status()) or {"connected": True, "selected_items": []}

    async def browse(self, folder_id: str | None = None) -> list[dict]:
        connector = await self._connector()
        try:
            items = await connector.list_folder(folder_id)
        except Exception as exc:
            raise ConnectorServiceError(
                "provider_unavailable",
                f"Could not list SharePoint folder: {exc}",
                retryable=True,
            ) from exc
        return [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "is_folder": "folder" in item,
                "size": item.get("size"),
                "web_url": item.get("webUrl", ""),
            }
            for item in items
        ]

    async def update_selection(self, items: list[SharePointSelectionItem]) -> dict:
        if await self._repository.status() is None:
            raise ConnectorServiceError(
                "authentication_required",
                "SharePoint is not connected — paste an access token first.",
            )
        await self._repository.save_selection(items)
        return (await self.status()) or {"connected": False, "selected_items": []}

    async def disconnect(self) -> None:
        await self._repository.clear()
        await self._cache.purge_source(SHAREPOINT_SOURCE)
