"""Microsoft Teams/Calendar connection use cases.

This service owns provider validation and current persistence coordination.
The legacy process-local token/settings implementations are temporary
adapters; HTTP routes and future AI tools depend only on this service.
"""

from __future__ import annotations

from loguru import logger

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.provider_ports import TokenInspector, TokenValidator
from backend.application.connectors.repositories import TeamsConnectionRepository


class TeamsConnectorService:
    def __init__(
        self,
        *,
        repository: TeamsConnectionRepository,
        token_inspector: TokenInspector,
        token_validator: TokenValidator,
    ) -> None:
        self._repository = repository
        self._token_inspector = token_inspector
        self._token_validator = token_validator

    async def status(self) -> dict[str, bool] | None:
        return await self._repository.status()

    async def connect(self, access_token: str) -> dict[str, bool]:
        token = access_token.strip()
        claims, scopes = self._token_inspector(token)
        missing = []
        if "Calendars.ReadWrite" not in set(scopes):
            missing.append("Calendars.ReadWrite")
        logger.info(
            "Teams login: tenant_id={} client_id={} expires_at={} "
            "delegated_scopes={} missing={}",
            claims.get("tid", "unknown"),
            claims.get("appid") or claims.get("azp", "unknown"),
            claims.get("exp", "unknown"),
            list(scopes),
            missing,
        )
        if missing:
            raise ConnectorServiceError(
                "permission_missing",
                "Teams/Calendar token is missing required delegated scope: "
                + ", ".join(missing),
            )

        try:
            await self._token_validator(token)
        except Exception as exc:
            raise ConnectorServiceError(
                "connection_failed",
                f"Could not connect to Teams: {exc}",
                retryable=True,
            ) from exc

        await self._repository.save_connected(token)
        return {"connected": True}

    async def disconnect(self) -> None:
        await self._repository.clear()
