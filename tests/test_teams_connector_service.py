import asyncio
import pytest
from fastapi import HTTPException

from backend.api.routes.connectors import teams as teams_route
from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors import teams as teams_service_module


class FakeTeamsRepository:
    def __init__(self, status=None) -> None:
        self.current_status = status
        self.saved_token: str | None = None
        self.cleared = False

    async def status(self):
        return self.current_status

    async def save_connected(self, access_token: str) -> None:
        self.saved_token = access_token
        self.current_status = {"connected": True}

    async def clear(self) -> None:
        self.cleared = True
        self.current_status = None


def test_service_rejects_missing_calendar_scope(monkeypatch) -> None:
    service = teams_service_module.TeamsConnectorService(repository=FakeTeamsRepository())
    monkeypatch.setattr(teams_service_module, "decode_token_claims", lambda _token: {})
    monkeypatch.setattr(teams_service_module, "delegated_scopes", lambda _token: ())

    with pytest.raises(ConnectorServiceError) as exc_info:
        asyncio.run(service.connect("token"))

    assert exc_info.value.code == "permission_missing"
    assert exc_info.value.retryable is False


def test_service_status_requires_config_and_live_token(monkeypatch) -> None:
    service = teams_service_module.TeamsConnectorService(
        repository=FakeTeamsRepository({"connected": False})
    )

    assert asyncio.run(service.status()) == {"connected": False}


def test_disconnect_delegates_to_repository() -> None:
    repository = FakeTeamsRepository({"connected": True})
    service = teams_service_module.TeamsConnectorService(repository=repository)

    asyncio.run(service.disconnect())

    assert repository.cleared is True


def test_route_maps_service_error_to_http_400(monkeypatch) -> None:
    async def fail(_token: str):
        raise ConnectorServiceError("permission_missing", "scope missing")

    monkeypatch.setattr(teams_route.teams_connector_service, "connect", fail)

    with pytest.raises(HTTPException, match="scope missing") as exc_info:
        asyncio.run(teams_route.put_teams(teams_route.TeamsConnect(access_token="token")))

    assert exc_info.value.status_code == 400
