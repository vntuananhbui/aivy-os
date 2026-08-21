import asyncio

from backend.application.connectors.jira_access import JiraAccessService
from backend.application.connectors.models import JiraCredentialData, SharePointSelectionItem
from backend.application.connectors.sharepoint_access import SharePointAccessService
from backend.infrastructure.connectors.base import ConnectorItem


class SharePointRepository:
    def __init__(self, selection):
        self.selection = selection

    async def status(self):
        return {"connected": True}

    async def get_access_token(self):
        return "token"

    async def get_selection(self):
        return self.selection


class SharePointClient:
    def __init__(self, token):
        self.token = token
        self.search_calls = []

    async def search(self, query, max_results=10):
        self.search_calls.append((query, max_results))
        return [ConnectorItem(id="picked-2", title="Content hit", url="https://sp/2")]

    async def fetch(self, item_id):
        return "x" * 9000


def test_sharepoint_access_intersects_content_search_with_selected_files() -> None:
    client = SharePointClient("token")
    repository = SharePointRepository([
        SharePointSelectionItem(id="picked-1", name="Other.pdf"),
        SharePointSelectionItem(id="picked-2", name="Document.pdf"),
    ])
    service = SharePointAccessService(repository, connector_factory=lambda _: client)

    result = asyncio.run(service.search("content phrase"))

    assert result["success"] is True
    assert result["scoped_to_picked"] is True
    assert [item["id"] for item in result["results"]] == ["picked-2"]


def test_sharepoint_access_pages_large_reads() -> None:
    client = SharePointClient("token")
    service = SharePointAccessService(SharePointRepository([]), connector_factory=lambda _: client)

    result = asyncio.run(service.read("item-1"))

    assert len(result["content"]) == 8000
    assert result["next_offset"] == 8000
    assert result["total_chars"] == 9000


class JiraRepository:
    async def status(self):
        return {"connected": True, "project_keys": ["AIVY"]}

    async def get_credential(self):
        return JiraCredentialData(site_url="https://jira.example", auth_mode="pat", personal_access_token="secret")


class JiraClient:
    def __init__(self, *args, **kwargs):
        self.project_keys = kwargs["project_keys"]

    async def search(self, query):
        return [ConnectorItem(id="AIVY-1", title="Issue", url="https://jira/AIVY-1", snippet="Task")]


def test_jira_access_builds_scoped_connector_from_repository_data() -> None:
    clients = []

    def factory(*args, **kwargs):
        client = JiraClient(*args, **kwargs)
        clients.append(client)
        return client

    result = asyncio.run(JiraAccessService(JiraRepository(), factory).execute("search", query="status != Done"))

    assert result["success"] is True
    assert result["results"][0]["id"] == "AIVY-1"
    assert clients[0].project_keys == ["AIVY"]
