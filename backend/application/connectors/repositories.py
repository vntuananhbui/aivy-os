"""Persistence ports consumed by connector application services."""

from __future__ import annotations

from typing import Protocol

from backend.application.connectors.models import JiraCredentialData, SharePointSelectionItem


class TeamsConnectionRepository(Protocol):
    async def status(self) -> dict[str, bool] | None: ...

    async def get_access_token(self) -> str | None: ...

    async def save_connected(self, access_token: str) -> None: ...

    async def clear(self) -> None: ...


class SharePointConnectionRepository(Protocol):
    async def status(self) -> dict | None: ...

    async def get_access_token(self) -> str | None: ...

    async def get_selection(self) -> list[SharePointSelectionItem]: ...

    async def save_connected(self, access_token: str) -> None: ...

    async def save_selection(self, items: list[SharePointSelectionItem]) -> None: ...

    async def clear(self) -> None: ...


class ConnectorCacheRepository(Protocol):
    async def purge_source(self, source: str) -> None: ...


class ConnectorCapabilityReader(Protocol):
    """Temporary synchronous snapshot used by synchronous graph builders."""

    def is_connected(self, source: str) -> bool: ...


class JiraConnectionRepository(Protocol):
    async def status(self) -> dict | None: ...

    async def get_credential(self) -> JiraCredentialData | None: ...

    async def save_connected(
        self,
        credential: JiraCredentialData,
        *,
        project_keys: list[str] | None = None,
        preserve_project_keys: bool = False,
    ) -> None: ...

    async def save_selection(self, project_keys: list[str]) -> None: ...

    async def clear(self) -> None: ...
