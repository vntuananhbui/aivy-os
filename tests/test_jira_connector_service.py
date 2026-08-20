import asyncio

import pytest

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors import jira as jira_service_module


class FakeJiraRepository:
    def __init__(self, status=None) -> None:
        self.current_status = status
        self.saved = None
        self.selection = []
        self.cleared = False

    async def status(self):
        return self.current_status

    async def save_connected(self, credential, **kwargs):
        self.saved = (credential, kwargs)

    async def save_selection(self, project_keys):
        self.selection = project_keys

    async def clear(self):
        self.cleared = True


class FakeCacheRepository:
    async def purge_source(self, source):
        pass


def _service(repository):
    return jira_service_module.JiraConnectorService(
        repository=repository,
        cache_repository=FakeCacheRepository(),
    )


def test_service_validates_cloud_credentials_before_provider_call() -> None:
    service = _service(FakeJiraRepository())

    with pytest.raises(ConnectorServiceError) as exc_info:
        asyncio.run(
            service.connect(
                jira_service_module.JiraConnectRequest(
                    site_url="https://example.atlassian.net",
                    auth_mode="cloud",
                )
            )
        )

    assert exc_info.value.code == "validation_error"


def test_service_status_combines_config_and_live_credential(monkeypatch) -> None:
    service = _service(
        FakeJiraRepository(
            {
                "connected": True,
                "site_url": "https://jira.example.com",
                "auth_mode": "server",
                "email": "",
                "project_keys": ["QACI"],
            }
        )
    )

    assert asyncio.run(service.status()) == {
        "connected": True,
        "site_url": "https://jira.example.com",
        "auth_mode": "server",
        "email": "",
        "project_keys": ["QACI"],
    }
