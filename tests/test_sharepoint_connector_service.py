import asyncio

import pytest
from fastapi import HTTPException

from backend.api.routes.connectors import sharepoint as sharepoint_route
from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors import sharepoint as sharepoint_service_module


class FakeSharePointRepository:
    def __init__(self, status=None, token=None) -> None:
        self.current_status = status
        self.token = token
        self.selection = []
        self.cleared = False

    async def status(self):
        return self.current_status

    async def get_access_token(self):
        return self.token

    async def save_connected(self, access_token):
        self.token = access_token

    async def save_selection(self, items):
        self.selection = items

    async def clear(self):
        self.cleared = True


class FakeTeamsRepository:
    async def status(self):
        return None

    async def save_connected(self, access_token):
        pass

    async def clear(self):
        pass


class FakeCacheRepository:
    async def purge_source(self, source):
        pass


def _service(repository):
    return sharepoint_service_module.SharePointConnectorService(
        repository=repository,
        teams_repository=FakeTeamsRepository(),
        cache_repository=FakeCacheRepository(),
        connector_factory=lambda _token: None,
        token_inspector=lambda _token: ({}, ()),
    )


def test_service_requires_token_before_browse(monkeypatch) -> None:
    service = _service(FakeSharePointRepository())

    with pytest.raises(ConnectorServiceError) as exc_info:
        asyncio.run(service.browse())

    assert exc_info.value.code == "authentication_required"


def test_service_status_preserves_selected_items(monkeypatch) -> None:
    service = _service(
        FakeSharePointRepository(
            status={
                "connected": True,
                "selected_items": [{"id": "file-1", "name": "Report.pdf"}],
            },
            token="token",
        )
    )

    assert asyncio.run(service.status()) == {
        "connected": True,
        "selected_items": [{"id": "file-1", "name": "Report.pdf"}],
    }


def test_browse_route_maps_auth_error_to_http_400(monkeypatch) -> None:
    async def fail(_folder_id=None):
        raise ConnectorServiceError("authentication_required", "connect first")

    monkeypatch.setattr(sharepoint_route.sharepoint_connector_service, "browse", fail)

    with pytest.raises(HTTPException, match="connect first") as exc_info:
        asyncio.run(sharepoint_route.browse_sharepoint())

    assert exc_info.value.status_code == 400
