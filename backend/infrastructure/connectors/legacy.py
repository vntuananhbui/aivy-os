"""Adapters over the current process-global connector persistence.

These keep behavior stable while application services move to repository
ports. They are replaced by user-scoped database repositories later.
"""

from __future__ import annotations

from backend.infrastructure.settings import store as settings_store
from backend.infrastructure.settings.store import SharePointItem
from backend.application.connectors.models import JiraCredentialData, SharePointSelectionItem
from backend.infrastructure.connectors import cache
from backend.infrastructure.connectors.jira import token_store as jira_token_store
from backend.infrastructure.connectors.sharepoint import token_store as sharepoint_token_store
from backend.infrastructure.connectors.teams import token_store as teams_token_store
from searchos.config.web_overlay import JiraConnection, SharePointConnection, TeamsConnection


class LegacyTeamsConnectionRepository:
    async def status(self) -> dict[str, bool] | None:
        config = settings_store.store.connectors.teams
        if config is None:
            return None
        return {
            "connected": bool(config.connected and teams_token_store.get_token())
        }

    async def get_access_token(self) -> str | None:
        return teams_token_store.get_token()

    async def save_connected(self, access_token: str) -> None:
        teams_token_store.set_token(access_token)

        def patch(settings):
            settings.connectors.teams = TeamsConnection(connected=True)

        await settings_store.update(patch)

    async def clear(self) -> None:
        teams_token_store.clear_token()

        def patch(settings):
            settings.connectors.teams = None

        await settings_store.update(patch)


class LegacySharePointConnectionRepository:
    async def status(self) -> dict | None:
        config = settings_store.store.connectors.sharepoint
        if config is None:
            return None
        return {
            "connected": bool(
                config.connected and sharepoint_token_store.get_token()
            ),
            "selected_items": [item.model_dump() for item in config.selected_items],
        }

    async def get_access_token(self) -> str | None:
        return sharepoint_token_store.get_token()

    async def get_selection(self) -> list[SharePointSelectionItem]:
        config = settings_store.store.connectors.sharepoint
        if config is None:
            return []
        return [
            SharePointSelectionItem(
                id=item.id,
                name=item.name,
                path=item.path or "",
                web_url=item.web_url or "",
                is_folder=item.is_folder,
            )
            for item in config.selected_items
        ]

    async def save_connected(self, access_token: str) -> None:
        sharepoint_token_store.set_token(access_token)

        def patch(settings):
            existing = (
                settings.connectors.sharepoint.selected_items
                if settings.connectors.sharepoint
                else []
            )
            settings.connectors.sharepoint = SharePointConnection(
                connected=True,
                selected_items=existing,
            )

        await settings_store.update(patch)

    async def save_selection(self, items: list[SharePointSelectionItem]) -> None:
        def patch(settings):
            if settings.connectors.sharepoint is None:
                raise RuntimeError("SharePoint connection is missing")
            settings.connectors.sharepoint.selected_items = [
                SharePointItem(
                    id=item.id,
                    name=item.name,
                    path=item.path,
                    web_url=item.web_url,
                    is_folder=item.is_folder,
                )
                for item in items
            ]

        await settings_store.update(patch)

    async def clear(self) -> None:
        sharepoint_token_store.clear_token()

        def patch(settings):
            settings.connectors.sharepoint = None

        await settings_store.update(patch)


class LegacyConnectorCacheRepository:
    async def purge_source(self, source: str) -> None:
        await cache.purge_all(source)


class LegacyConnectorCapabilityReader:
    """Read current process-global connector readiness without leaking stores."""

    def is_connected(self, source: str) -> bool:
        if source == "sharepoint":
            config = settings_store.store.connectors.sharepoint
            return bool(
                config is not None
                and config.connected
                and sharepoint_token_store.get_token()
            )
        if source == "jira":
            config = settings_store.store.connectors.jira
            return bool(
                config is not None
                and config.connected
                and jira_token_store.get_credential() is not None
            )
        if source in ("teams", "calendar"):
            config = settings_store.store.connectors.teams
            return bool(
                config is not None
                and config.connected
                and teams_token_store.get_token()
            )
        return False


class LegacyJiraConnectionRepository:
    async def status(self) -> dict | None:
        config = settings_store.store.connectors.jira
        if config is None:
            return None
        return {
            "connected": bool(
                config.connected and jira_token_store.get_credential()
            ),
            "site_url": config.site_url,
            "auth_mode": config.auth_mode,
            "email": config.email,
            "project_keys": list(config.project_keys),
        }

    async def get_credential(self) -> JiraCredentialData | None:
        credential = jira_token_store.get_credential()
        if credential is None:
            return None
        return JiraCredentialData(
            site_url=credential.site_url,
            auth_mode=credential.auth_mode,
            email=credential.email,
            api_token=credential.api_token,
            personal_access_token=credential.personal_access_token,
            access_token=credential.access_token,
            expires_at=credential.expires_at or 0.0,
            cloud_id=credential.cloud_id,
        )

    async def save_connected(
        self,
        credential: JiraCredentialData,
        *,
        project_keys: list[str] | None = None,
        preserve_project_keys: bool = False,
    ) -> None:
        jira_token_store.set_credential(
            jira_token_store.JiraCredential(
                site_url=credential.site_url,
                auth_mode=credential.auth_mode,
                email=credential.email,
                api_token=credential.api_token,
                personal_access_token=credential.personal_access_token,
                access_token=credential.access_token,
                expires_at=credential.expires_at,
                cloud_id=credential.cloud_id,
            )
        )

        def patch(settings):
            selected_projects = project_keys or []
            if preserve_project_keys and settings.connectors.jira:
                selected_projects = settings.connectors.jira.project_keys
            settings.connectors.jira = JiraConnection(
                connected=True,
                site_url=credential.site_url,
                auth_mode=credential.auth_mode,
                email=credential.email,
                project_keys=selected_projects,
            )

        await settings_store.update(patch)

    async def save_selection(self, project_keys: list[str]) -> None:
        def patch(settings):
            if settings.connectors.jira is None:
                raise RuntimeError("Jira connection is missing")
            settings.connectors.jira.project_keys = project_keys

        await settings_store.update(patch)

    async def clear(self) -> None:
        jira_token_store.clear_credential()

        def patch(settings):
            settings.connectors.jira = None

        await settings_store.update(patch)
