import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors import jira_oauth


class FakeStateRepository:
    def __init__(self, *, consume_result: bool = True) -> None:
        self.consume_result = consume_result
        self.consumed: list[str] = []

    async def create(self) -> str:
        return "oauth-state"

    async def consume(self, state: str) -> bool:
        self.consumed.append(state)
        return self.consume_result


class FakeJiraService:
    def __init__(self) -> None:
        self.saved: dict | None = None

    async def save_oauth_connection(self, **kwargs):
        self.saved = kwargs
        return {"connected": True}


class FakeResponse:
    def __init__(self, status_code: int, data) -> None:
        self.status_code = status_code
        self._data = data
        self.content = b"data"
        self.text = str(data)

    def json(self):
        return self._data


class FakeHttpClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, _url, **_kwargs):
        return FakeResponse(200, {"access_token": "access-token", "expires_in": 3600})

    async def get(self, _url, **_kwargs):
        return FakeResponse(
            200,
            [{"id": "cloud-1", "url": "https://example.atlassian.net"}],
        )


def _set_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv("JIRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("JIRA_SECRET", "client-secret")
    monkeypatch.setenv("JIRA_REDIRECT_URI", "https://app.example/callback")


def test_authorization_url_uses_repository_state(monkeypatch) -> None:
    _set_oauth_env(monkeypatch)
    service = jira_oauth.JiraOAuthService(
        state_repository=FakeStateRepository(),
        jira_service=FakeJiraService(),
    )

    url = urlsplit(asyncio.run(service.authorization_url()))
    query = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == jira_oauth.JIRA_AUTHORIZE_URL
    assert query["state"] == ["oauth-state"]
    assert query["client_id"] == ["client-id"]


def test_complete_rejects_invalid_state_before_network(monkeypatch) -> None:
    _set_oauth_env(monkeypatch)
    service = jira_oauth.JiraOAuthService(
        state_repository=FakeStateRepository(consume_result=False),
        jira_service=FakeJiraService(),
    )

    with pytest.raises(ConnectorServiceError) as exc_info:
        asyncio.run(service.complete(state="bad-state", code="code"))

    assert exc_info.value.code == "oauth_state_invalid"


def test_complete_persists_first_accessible_resource(monkeypatch) -> None:
    _set_oauth_env(monkeypatch)
    monkeypatch.setattr(jira_oauth.httpx, "AsyncClient", FakeHttpClient)
    jira_service = FakeJiraService()
    service = jira_oauth.JiraOAuthService(
        state_repository=FakeStateRepository(),
        jira_service=jira_service,
    )

    result = asyncio.run(service.complete(state="oauth-state", code="code"))

    assert result.site_url == "https://example.atlassian.net"
    assert result.cloud_id == "cloud-1"
    assert jira_service.saved is not None
    assert jira_service.saved["access_token"] == "access-token"
    assert jira_service.saved["cloud_id"] == "cloud-1"
