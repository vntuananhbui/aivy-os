"""Connector service composition for the current deployment."""

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

teams_connection_repository = LegacyTeamsConnectionRepository()
connector_capability_reader = LegacyConnectorCapabilityReader()
teams_connector_service = TeamsConnectorService(repository=teams_connection_repository)
calendar_access_service = CalendarAccessService(repository=teams_connection_repository)
sharepoint_connection_repository = LegacySharePointConnectionRepository()
connector_cache_repository = LegacyConnectorCacheRepository()
sharepoint_connector_service = SharePointConnectorService(
    repository=sharepoint_connection_repository,
    teams_repository=teams_connection_repository,
    cache_repository=connector_cache_repository,
)
sharepoint_access_service = SharePointAccessService(
    repository=sharepoint_connection_repository,
)
jira_connection_repository = LegacyJiraConnectionRepository()
jira_connector_service = JiraConnectorService(
    repository=jira_connection_repository,
    cache_repository=connector_cache_repository,
)
jira_access_service = JiraAccessService(repository=jira_connection_repository)
jira_oauth_state_repository = InMemoryOAuthStateRepository(
    ttl_seconds=OAUTH_STATE_TTL
)
jira_oauth_service = JiraOAuthService(
    state_repository=jira_oauth_state_repository,
    jira_service=jira_connector_service,
)
