"""Connector service composition for the current deployment."""

import httpx

from backend.application.connectors.teams import TeamsConnectorService
from backend.application.connectors.calendar_access import CalendarAccessService
from backend.application.connectors.sharepoint import SharePointConnectorService
from backend.application.connectors.jira import JiraConnectorService
from backend.application.connectors.jira_access import JiraAccessService
from backend.application.connectors.sharepoint_access import SharePointAccessService
from backend.application.connectors.jira_oauth import (
    OAUTH_STATE_TTL,
    JiraOAuthService,
)
from backend.application.connectors.oauth_state import InMemoryOAuthStateRepository
from backend.infrastructure.connectors.legacy import (
    LegacyConnectorCacheRepository,
    LegacyConnectorCapabilityReader,
    LegacyJiraConnectionRepository,
    LegacySharePointConnectionRepository,
    LegacyTeamsConnectionRepository,
)
from backend.infrastructure.connectors.jira import JiraConnector
from backend.infrastructure.connectors.microsoft_graph import GraphAuth, TeamsMeetingClient
from backend.infrastructure.connectors.microsoft_graph.auth import (
    decode_token_claims,
    delegated_scopes,
)
from backend.infrastructure.connectors.microsoft_graph.client import GRAPH_BASE
from backend.infrastructure.connectors.sharepoint import SharePointConnector


def inspect_graph_token(token: str) -> tuple[dict, tuple[str, ...]]:
    return decode_token_claims(token), delegated_scopes(token)


async def validate_graph_token(token: str) -> None:
    auth = GraphAuth(token)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {await auth.get_token()}"},
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Graph GET /me -> {response.status_code}: {response.text}"
        )


def calendar_client_factory(token: str) -> TeamsMeetingClient:
    return TeamsMeetingClient(GraphAuth(token))

teams_connection_repository = LegacyTeamsConnectionRepository()
connector_capability_reader = LegacyConnectorCapabilityReader()
teams_connector_service = TeamsConnectorService(
    repository=teams_connection_repository,
    token_inspector=inspect_graph_token,
    token_validator=validate_graph_token,
)
calendar_access_service = CalendarAccessService(
    repository=teams_connection_repository,
    client_factory=calendar_client_factory,
)
sharepoint_connection_repository = LegacySharePointConnectionRepository()
connector_cache_repository = LegacyConnectorCacheRepository()
sharepoint_connector_service = SharePointConnectorService(
    repository=sharepoint_connection_repository,
    teams_repository=teams_connection_repository,
    cache_repository=connector_cache_repository,
    connector_factory=SharePointConnector,
    token_inspector=inspect_graph_token,
)
sharepoint_access_service = SharePointAccessService(
    repository=sharepoint_connection_repository,
    connector_factory=SharePointConnector,
)
jira_connection_repository = LegacyJiraConnectionRepository()
jira_connector_service = JiraConnectorService(
    repository=jira_connection_repository,
    cache_repository=connector_cache_repository,
    connector_factory=JiraConnector,
)
jira_access_service = JiraAccessService(
    repository=jira_connection_repository,
    connector_factory=JiraConnector,
)
jira_oauth_state_repository = InMemoryOAuthStateRepository(
    ttl_seconds=OAUTH_STATE_TTL
)
jira_oauth_service = JiraOAuthService(
    state_repository=jira_oauth_state_repository,
    jira_service=jira_connector_service,
)
